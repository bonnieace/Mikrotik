"""Generate and claim one-time, idempotent RouterOS onboarding scripts.

The script touches only Uzanet-owned objects, creates a pre-change backup, and aborts when
an object with a reserved name exists without the Uzanet ownership marker.
"""

from __future__ import annotations

import ipaddress
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import AdminUser, Router
from database.session import SessionLocal
from schemas import RouterOnboardingRequest
from security import decrypt_secret, encrypt_secret, hash_token, random_token
from services.vpn_agent_service import provision_l2tp_peer, revoke_l2tp_peer, vpn_agent_enabled
from settings import get_settings


MANAGED_COMMENT = "uzanet-managed"


def _ros_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def _api_username(router_uid: str) -> str:
    return f"uzanet-{router_uid.split('-')[0]}"


def _l2tp_username(router_uid: str) -> str:
    return f"router-{router_uid}"


def _valid_claim_ip(value: str) -> str:
    raw = value.split("/")[0]
    try:
        address = ipaddress.ip_address(raw)
        allowed = [ipaddress.ip_network(item, strict=False) for item in get_settings().router_allowed_cidrs]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid router tunnel address") from exc
    if not any(address in network for network in allowed):
        raise HTTPException(status_code=422, detail="Router address is outside the configured control network")
    return str(address)


def _fetch_compatible(command: str, arguments: str = "") -> str:
    """Probe syntax without network I/O; RouterOS <7.18 cannot follow redirects.

    Keep unsupported options inside :parse strings so v6 can parse the outer RSC.
    Catch only compilation, never fetch execution: HTTP failure must not redeem a
    one-time capability again or retry a registration request.
    """
    modern = _ros_quote(command + " http-max-redirect-count=0")
    legacy = _ros_quote(command)
    return (
        ':local uzanetFetch; '
        f':do {{ :set uzanetFetch [:parse "{modern}"] }} '
        f'on-error={{ :set uzanetFetch [:parse "{legacy}"] }}; '
        f'$uzanetFetch{arguments}'
    )


def _build_script(router: Router, claim_token: str, api_password: str, l2tp_password: str, replace_managed_tunnel: bool = False) -> str:
    settings = get_settings()
    values = {
        "backup": _ros_quote(f"uzanet-pre-onboard-{router.uid.split('-')[0]}"),
        "comment": MANAGED_COMMENT,
        "expected_ip": _ros_quote(router.ip_address if router.ip_address != "0.0.0.0" else ""),
        "host": _ros_quote(settings.router_control_host),
        "cidr": _ros_quote(settings.router_control_cidr),
        "api_user": _ros_quote(router.username),
        "api_password": _ros_quote(api_password),
        "l2tp_user": _ros_quote(_l2tp_username(router.uid)),
        "l2tp_password": _ros_quote(l2tp_password),
        "claim_url": _ros_quote(f"{settings.api_public_url}/api/v1/router-onboarding/claim"),
        "token": _ros_quote(claim_token),
    }
    claim_fetch = _fetch_compatible(
        f'/tool fetch url="{values["claim_url"]}" check-certificate=yes '
        'http-method=post http-header-field="Content-Type: application/json" '
        'http-data=$body keep-result=no',
        ' body=$claimBody',
    )
    return rf'''# Uzanet managed onboarding — one-time token, expires automatically
# This script preserves WAN/default routes and aborts on reserved-name conflicts.
:local managedComment "{values['comment']}"
:local tunnelName "uzanet-control"
:local groupName "uzanet-api"
:local apiUser "{values['api_user']}"
:local replaceTunnel {"true" if replace_managed_tunnel else "false"}

:if ([:len [/file find where name="{values['backup']}.backup"]] = 0) do={{
  /system backup save name="{values['backup']}"
}}

:local existingTunnel [/interface l2tp-client find where name=$tunnelName]
:if ([:len $existingTunnel] > 0) do={{
  :if ([/interface l2tp-client get $existingTunnel comment] != $managedComment) do={{
    :error "Uzanet onboarding stopped: conflicting l2tp-client named uzanet-control"
  }}
  :if ([/interface l2tp-client get $existingTunnel user] != "{values['l2tp_user']}") do={{
    :if (!$replaceTunnel) do={{ :error "Existing Uzanet tunnel belongs to another router record. Enable replacement explicitly or use that record." }}
    /interface l2tp-client disable $existingTunnel
  }}
  /interface l2tp-client set $existingTunnel connect-to="{values['host']}" user="{values['l2tp_user']}" password="{values['l2tp_password']}" allow=mschap2 add-default-route=no use-peer-dns=no disabled=no
}} else={{
  /interface l2tp-client add name=$tunnelName comment=$managedComment connect-to="{values['host']}" user="{values['l2tp_user']}" password="{values['l2tp_password']}" allow=mschap2 add-default-route=no use-peer-dns=no disabled=no
}}

:local existingGroup [/user group find where name=$groupName]
:if ([:len $existingGroup] = 0) do={{
  /user group add name=$groupName policy=read,write,test,api
}}

:local existingUser [/user find where name=$apiUser]
:if ([:len $existingUser] > 0) do={{
  :if ([/user get $existingUser comment] != $managedComment) do={{
    :error "Uzanet onboarding stopped: conflicting RouterOS user"
  }}
  /user set $existingUser group=$groupName password="{values['api_password']}" address="{values['cidr']}" disabled=no
}} else={{
  /user add name=$apiUser group=$groupName password="{values['api_password']}" address="{values['cidr']}" comment=$managedComment disabled=no
}}

:if ([/ip service get api disabled]) do={{ /ip service enable api }}

:local tunnelAddress ""
:for attempt from=1 to=12 do={{
  :local addrId [/ip address find where interface=$tunnelName]
  :if ([:len $addrId] = 1) do={{
    :local candidate [/ip address get $addrId address]
    :local candidateIP [:pick $candidate 0 [:find $candidate "/"]]
    :if (("{values['expected_ip']}" = "") || ($candidateIP = "{values['expected_ip']}")) do={{ :set tunnelAddress $candidate }}
  }}
  :if ([:len $tunnelAddress] > 0) do={{ :break }}
  :delay 5s
}}
:if ([:len $tunnelAddress] = 0) do={{ :error "Uzanet tunnel did not receive an address" }}

:local rosVersion [/system resource get version]
:local claimBody ("{{\"token\":\"{values['token']}\",\"tunnel_ip\":\"" . $tunnelAddress . "\",\"routeros_version\":\"" . $rosVersion . "\"}}")
{claim_fetch}
:put "Uzanet registration accepted. Check connection status in the portal."
'''


def create_onboarding(body: RouterOnboardingRequest, current_user: AdminUser) -> dict:
    settings = get_settings()
    if not settings.router_control_host:
        raise HTTPException(status_code=503, detail="Router control host is not configured")
    public_url = urlsplit(settings.api_public_url)
    if public_url.scheme != "https" or not public_url.hostname or public_url.username or public_url.password or public_url.query or public_url.fragment or public_url.path:
        raise HTTPException(status_code=503, detail="Router onboarding requires an HTTPS API_PUBLIC_URL origin")
    if body.payment_provider not in settings.payment_providers:
        raise HTTPException(status_code=422, detail="Payment provider is not enabled")

    api_password = secrets.token_urlsafe(24)
    l2tp_password = secrets.token_urlsafe(24)
    claim_token = random_token()
    peer_username: str | None = None
    peer_provisioned = False
    db = SessionLocal()
    try:
        router = crud.create_router(
            db,
            name=body.name,
            ip_address="0.0.0.0",
            port=8728,
            username="pending",
            password=encrypt_secret(api_password),
            owner_id=current_user.id,
            portal_slug=body.portal_slug,
            portal_enabled=True,
            payment_provider=body.payment_provider,
            connection_mode="l2tp",
            onboarding_status="pending",
            onboarding_token_hash=hash_token(claim_token),
            onboarding_token_expires_at=datetime.utcnow() + timedelta(minutes=settings.onboarding_token_minutes),
        )
        router.username = _api_username(router.uid)
        peer_username = _l2tp_username(router.uid)
        if vpn_agent_enabled():
            assigned_ip = provision_l2tp_peer(peer_username, l2tp_password)
            peer_provisioned = True
            router.ip_address = _valid_claim_ip(assigned_ip)
        crud.create_log(db, "Router onboarding created", router_id=router.id, event_type="router.onboarding.created")
        script = _build_script(router, claim_token, api_password, l2tp_password, body.replace_managed_tunnel)
        download_token = secrets.token_urlsafe(32)
        router.onboarding_download_hash = hash_token(download_token)
        router.onboarding_script_encrypted = encrypt_secret(script)
        db.commit()
        db.refresh(router)
        download_url = f"{settings.api_public_url}/api/v1/router-onboarding/{router.uid}/script"
        return {
            "router": serialize_router(router),
            "expires_at": router.onboarding_token_expires_at,
            "script": script,
            "download_url": download_url,
            "install_command": _install_command(router.uid, download_url, download_token),
            "l2tp_peer": {
                "username": peer_username,
                "password": l2tp_password,
                "ip_address": None if router.ip_address == "0.0.0.0" else router.ip_address,
                "provisioned": peer_provisioned,
            },
        }
    except Exception as exc:
        db.rollback()
        if peer_provisioned and peer_username:
            try:
                revoke_l2tp_peer(peer_username)
            except Exception:
                pass
        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail="Portal slug is already in use") from exc
        raise
    finally:
        db.close()



def _install_command(router_uid: str, url: str, token: str) -> str:
    # Token travels in a header, never in URLs/access logs. The outer block preserves
    # scope in a pasted terminal command. Never import after a failed fetch.
    filename = _ros_quote(f"uzanet-{router_uid}.rsc")
    fetch = _fetch_compatible(
        f'/tool fetch url="{_ros_quote(url)}" '
        f'http-header-field="X-Onboarding-Token: {token}" '
        f'check-certificate=yes dst-path="{filename}"'
    )
    return (
        f':do {{ {fetch}; '
        f':do {{ /import file-name="{filename}" }} on-error={{ '
        f'/file remove [find where name="{filename}"]; '
        ':error "Setup failed. Check router state; use the saved RSC to retry before expiry." }; '
        f'/file remove [find where name="{filename}"] '
        f'}} on-error={{ :do {{ /file remove [find where name="{filename}"] }} on-error={{}}; '
        ':error "Onboarding did not complete. Check connectivity, certificates, link expiry and router configuration." }'
    )


def consume_onboarding_script(router_uid: str, token: str) -> str:
    """Atomically redeem a scoped download capability, independently of claim."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(status_code=404, detail="Onboarding download is unavailable")
    db = SessionLocal()
    try:
        query = db.query(Router).filter(
            Router.uid == router_uid,
            Router.onboarding_download_hash == hash_token(token),
            Router.onboarding_token_expires_at > datetime.utcnow(),
            Router.onboarding_status == "pending",
            Router.onboarding_script_encrypted.isnot(None),
            Router.owner_id.in_(db.query(AdminUser.id).filter(AdminUser.is_active.is_(True))),
        )
        router = query.first()
        if router is None:
            raise HTTPException(status_code=404, detail="Onboarding download is unavailable")
        script = decrypt_secret(router.onboarding_script_encrypted)
        # Conditional UPDATE is also safe with multiple workers; only one wins.
        changed = query.update({
            Router.onboarding_download_hash: None,
            Router.onboarding_script_encrypted: None,
        }, synchronize_session=False)
        if changed != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="Onboarding download is unavailable")
        db.commit()
        return script
    finally:
        db.close()


def expire_onboarding_downloads() -> int:
    with SessionLocal() as db:
        count = db.query(Router).filter(
            Router.onboarding_token_expires_at <= datetime.utcnow(),
            Router.onboarding_script_encrypted.isnot(None),
        ).update({Router.onboarding_download_hash: None, Router.onboarding_script_encrypted: None}, synchronize_session=False)
        db.commit()
        return count


def claim_onboarding(token: str, tunnel_ip: str, routeros_version: str | None) -> dict:
    now = datetime.utcnow()
    token_digest = hash_token(token)
    db = SessionLocal()
    try:
        router = (
            db.query(Router)
            .filter(Router.onboarding_token_hash == token_digest)
            .with_for_update()
            .first()
        )
        if router is None:
            raise HTTPException(status_code=404, detail="Onboarding token is invalid")
        if router.onboarding_token_expires_at is None or router.onboarding_token_expires_at < now:
            raise HTTPException(status_code=410, detail="Onboarding token has expired")
        if router.onboarding_status == "claimed":
            return {"status": "claimed", "router_uid": router.uid}

        claimed_ip = _valid_claim_ip(tunnel_ip)
        if router.ip_address not in {None, "0.0.0.0", claimed_ip}:
            raise HTTPException(status_code=409, detail="Router tunnel address does not match its provisioned peer")
        router.ip_address = claimed_ip
        router.routeros_version = re.sub(r"[^A-Za-z0-9 ._()-]", "", routeros_version or "")[:64] or None
        router.onboarding_download_hash = None
        router.onboarding_script_encrypted = None
        router.onboarding_status = "claimed"
        router.last_seen_at = now
        router.last_error = None
        crud.create_log(db, "Router onboarding claimed", router_id=router.id, event_type="router.onboarding.claimed")
        db.commit()
        return {"status": "claimed", "router_uid": router.uid}
    finally:
        db.close()


def serialize_router(router: Router) -> dict:
    return {
        "uid": router.uid,
        "name": router.name,
        "ip_address": router.ip_address,
        "port": router.port,
        "username": router.username,
        "portal_slug": router.portal_slug,
        "portal_enabled": router.portal_enabled,
        "payment_provider": router.payment_provider,
        "connection_mode": router.connection_mode,
        "onboarding_status": router.onboarding_status,
        "last_seen_at": router.last_seen_at,
        "last_error": router.last_error,
        "routeros_version": router.routeros_version,
        "created_at": router.created_at,
        "updated_at": router.updated_at,
    }
