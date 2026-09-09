from __future__ import annotations

import pytest
from fastapi import HTTPException

from database.models import AdminUser, Router
from schemas import RouterOnboardingRequest
from security import is_encrypted
from services import onboarding_service
from services.onboarding_service import claim_onboarding, create_onboarding
from services.router_service import get_router_for_user


def _user(db, username: str, role: str = "isp") -> AdminUser:
    row = AdminUser(username=username, hashed_password="not-used", role=role)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_onboarding_is_safe_scoped_and_idempotent(db, monkeypatch):
    user = _user(db, "isp-one")
    token = "claim-token-with-more-than-thirty-two-characters"
    monkeypatch.setattr(onboarding_service, "random_token", lambda: token)
    provisioned = {}
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: True)
    monkeypatch.setattr(
        onboarding_service,
        "provision_l2tp_peer",
        lambda username, password: provisioned.update(username=username, password=password) or "10.77.0.12",
    )
    response = create_onboarding(
        RouterOnboardingRequest(name="Branch Router", portal_slug="branch-router", payment_provider="mpesa"),
        user,
    )
    script = response["script"]
    assert "/system backup save" in script
    assert "add-default-route=no" in script
    assert "use-peer-dns=no" in script
    assert "profile=default allow=chap use-ipsec=no" in script
    assert "allow=mschap2" not in script
    assert "allow=pap" not in script
    assert ":break" not in script
    assert "uzanet-managed" in script
    assert "reset-configuration" not in script
    assert response["tls_preflight_command"].endswith('/health/live" check-certificate=yes keep-result=no')
    assert response["legacy_ca_common_name"] == "ISRG Root X1"
    assert response["l2tp_peer"]["password"] not in repr(response["router"])
    assert response["l2tp_peer"]["provisioned"] is True
    assert response["l2tp_peer"]["ip_address"] == "10.77.0.12"
    assert provisioned["username"] == response["l2tp_peer"]["username"]

    router = db.query(Router).filter(Router.uid == response["router"]["uid"]).first()
    assert is_encrypted(router.password)
    assert token not in router.password

    first = claim_onboarding(token, "10.77.0.12/32", "7.15.3")
    second = claim_onboarding(token, "10.77.0.12/32", "7.15.3")
    assert first == second == {"status": "claimed", "router_uid": router.uid}


def test_router_lookup_hides_other_tenants_router(db):
    owner = _user(db, "owner")
    stranger = _user(db, "stranger")
    router = Router(
        name="Private",
        ip_address="10.77.0.9",
        username="api-user",
        password="encrypted-placeholder",
        owner_id=owner.id,
        portal_slug="private-router",
    )
    db.add(router)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        get_router_for_user(router.uid, stranger)
    assert exc.value.status_code == 404


# Decode the generated RouterOS string fragments so tests catch escaping bugs in
# emitted RSC, rather than only checking Python source templates.
def test_generated_claim_json_and_scoped_download(db, monkeypatch):
    import json
    import re
    from security import decrypt_secret, hash_token
    from services.onboarding_service import consume_onboarding_script
    owner = _user(db, "download-owner")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)
    bundle = create_onboarding(RouterOnboardingRequest(name="Download test", portal_slug="download-test"), owner)
    line = next(line for line in bundle["script"].splitlines() if line.startswith(":local claimBody"))
    expression = line[len(":local claimBody ("):-1]
    fragments = re.split(r" \. ", expression)
    substitutions = {"$tunnelAddress": "10.77.0.15/32", "$rosVersion": "7.20"}
    decoded = "".join(substitutions[x] if x in substitutions else json.loads(x) for x in fragments)
    claim = json.loads(decoded)
    assert claim["tunnel_ip"] == "10.77.0.15/32"
    assert claim["routeros_version"] == "7.20"
    command = bundle["install_command"]
    token = re.search(r"X-Onboarding-Token: ([A-Za-z0-9_-]+)", command).group(1)
    assert token not in bundle["download_url"]
    assert claim["token"] != token
    assert "check-certificate=yes" in command
    assert "http-max-redirect-count=0" in command
    assert command.index("/tool fetch") < command.index("/import")
    assert "/file remove" in command
    router = db.query(Router).filter_by(uid=bundle["router"]["uid"]).one()
    assert router.onboarding_download_hash == hash_token(token)
    assert decrypt_secret(router.onboarding_script_encrypted) == bundle["script"]
    assert token not in router.onboarding_script_encrypted
    with pytest.raises(HTTPException):
        consume_onboarding_script("different-router", token)
    with pytest.raises(HTTPException):
        consume_onboarding_script(router.uid, claim["token"])
    assert consume_onboarding_script(router.uid, token) == bundle["script"]
    assert consume_onboarding_script(router.uid, token) == bundle["script"]
    db.refresh(router)
    assert router.onboarding_script_encrypted is not None
    assert router.onboarding_download_hash == hash_token(token)
    assert router.onboarding_status == "pending"
    # Download retries must not consume the separate claim capability.
    assert claim_onboarding(claim["token"], "10.77.0.15", "7.20")["status"] == "claimed"
    db.refresh(router)
    assert router.onboarding_script_encrypted is None
    assert router.onboarding_download_hash is None


@pytest.mark.parametrize("reason", ["expired", "claimed", "disabled", "deleted"])
def test_unavailable_downloads(db, monkeypatch, reason):
    import re
    from datetime import datetime, timedelta
    from services.onboarding_service import consume_onboarding_script, expire_onboarding_downloads
    owner = _user(db, "owner")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)
    bundle = create_onboarding(RouterOnboardingRequest(name="Branch", portal_slug="branch"), owner)
    token = re.search(r"X-Onboarding-Token: ([A-Za-z0-9_-]+)", bundle["install_command"]).group(1)
    router = db.query(Router).filter_by(uid=bundle["router"]["uid"]).one()
    if reason == "expired":
        router.onboarding_token_expires_at = datetime.utcnow() - timedelta(seconds=1)
    elif reason == "claimed":
        router.onboarding_status = "claimed"
    elif reason == "disabled":
        owner.is_active = False
    else:
        db.delete(router)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        consume_onboarding_script(bundle["router"]["uid"], token)
    assert exc.value.status_code == 404
    if reason == "expired":
        assert expire_onboarding_downloads() == 1
        db.refresh(router)
        assert router.onboarding_script_encrypted is None


def test_download_http_contract(db, monkeypatch):
    import re
    from fastapi.testclient import TestClient
    from mono import app
    owner = _user(db, "owner")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)
    bundle = create_onboarding(RouterOnboardingRequest(name="Branch", portal_slug="branch"), owner)
    token = re.search(r"X-Onboarding-Token: ([A-Za-z0-9_-]+)", bundle["install_command"]).group(1)
    url = f"/api/v1/router-onboarding/{bundle['router']['uid']}/script"
    client = TestClient(app)
    assert client.get(url).status_code == 404
    assert client.head(url, headers={"X-Onboarding-Token": token}).status_code == 405
    response = client.get(url, headers={"X-Onboarding-Token": token})
    assert response.status_code == 200
    assert response.text == bundle["script"]
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment" in response.headers["content-disposition"]
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["referrer-policy"] == "no-referrer"
    again = client.get(url, headers={"X-Onboarding-Token": token})
    assert again.status_code == 200
    assert again.text == bundle["script"]
    assert "no-store" in again.headers["cache-control"]


def test_replacement_requires_explicit_choice_and_keeps_backup(db, monkeypatch):
    owner = _user(db, "owner")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)
    for replace, slug in [(False, "safe"), (True, "replace")]:
        bundle = create_onboarding(RouterOnboardingRequest(name="Branch", portal_slug=slug, replace_managed_tunnel=replace), owner)
        script = bundle["script"]
        assert f':local replaceTunnel {str(replace).lower()}' in script
        assert ':if (!$replaceTunnel)' in script
        assert '/interface l2tp-client set $existingTunnel' in script
        assert script.index('comment] != $managedComment') < script.index('/interface l2tp-client disable')
        assert script.index('/file find where name=') < script.index('/system backup save')
        assert 'reset-configuration' not in script


def test_download_requires_https_before_creating_router(db, monkeypatch):
    monkeypatch.setenv("API_PUBLIC_URL", "http://api.test.invalid")
    onboarding_service.get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        create_onboarding(RouterOnboardingRequest(name="Branch", portal_slug="branch"), _user(db, "owner"))
    assert exc.value.status_code == 503
    assert db.query(Router).count() == 0



def test_concurrent_downloads_are_retry_safe(db, monkeypatch):
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from services.onboarding_service import consume_onboarding_script
    owner = _user(db, "owner")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)
    bundle = create_onboarding(RouterOnboardingRequest(name="Branch", portal_slug="branch"), owner)
    token = re.search(r"X-Onboarding-Token: ([A-Za-z0-9_-]+)", bundle["install_command"]).group(1)
    barrier = Barrier(2)
    decrypt = onboarding_service.decrypt_secret
    def synchronized_decrypt(value):
        barrier.wait(timeout=5)
        return decrypt(value)
    monkeypatch.setattr(onboarding_service, "decrypt_secret", synchronized_decrypt)
    def download():
        try:
            return consume_onboarding_script(bundle["router"]["uid"], token)
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: download(), range(2)))
    assert results == [bundle["script"], bundle["script"]]


def test_fetch_compatibility_probes_syntax_without_retrying_network():
    import json
    import re
    from services.onboarding_service import _fetch_compatible, _install_command
    def parsed_strings(source):
        # RouterOS strings escape dollar interpolation, unlike JSON strings.
        return [json.loads(x.replace(r'\$', '$')) for x in re.findall(r'\[:parse ("(?:\\.|[^"\\])*")\]', source)]
    command = '/tool fetch url="https://api.test.invalid/claim" check-certificate=yes http-data=$body'
    generated = _fetch_compatible(command, ' body=$claimBody')
    modern, legacy = parsed_strings(generated)
    assert modern == command + ' http-max-redirect-count=0'
    assert legacy == command
    # The old RouterOS parser sees no unsupported literal option; only :parse
    # sees it. On either version, the HTTP operation executes once after probing.
    without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', generated)
    assert 'http-max-redirect-count' not in without_strings
    assert generated.endswith('}; $uzanetFetch body=$claimBody')
    assert generated.count('$uzanetFetch body=') == 1
    install = _install_command('test-router', 'https://api.test.invalid/script', 'test-token')
    source = re.search(r':local c ("(?:\\.|[^"\\])*");', install).group(1)
    decoded = json.loads(source.replace(r'\$', '$'))
    assert 'check-certificate=yes' in decoded
    assert 'http-max-redirect-count' not in decoded
    assert 'dst-path=$path' in decoded
    assert '[:parse ($c." http-max-redirect-count=0")]' in install
    assert 'on-error={:set f [:parse $c]}' in install
    assert install.index('$f path=$p') < install.index('/import')


def test_install_command_is_compact_retains_failed_rsc_and_cleans_success():
    from services.onboarding_service import _install_command
    uid = '09aa2885-5984-4182-a9f8-8a12cc8e9c60'
    url = f'https://api.uzanet.co.ke/api/v1/router-onboarding/{uid}/script'
    token = 'a' * 43
    command = _install_command(uid, url, token)
    assert len(command) < 950
    assert '\n' not in command
    assert command.count(token) == 1
    assert command.count(url) == 1
    assert command.count(f'uzanet-{uid}.rsc') == 1
    assert ':do {$f path=$p} on-error={:set e true};' in command
    assert ':do {/import file-name=$p} on-error={:set e true};' in command
    assert 'Download failed; check connection, clock and CA trust' in command
    assert 'Setup failed; downloaded RSC was kept for retry' in command
    assert command.index('/file remove') < command.index('$f path=$p')
    assert command.rindex('/file remove') > command.index('downloaded RSC was kept for retry')
