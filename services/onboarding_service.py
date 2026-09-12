"""Generate, download, and claim idempotent RouterOS onboarding scripts.

The script keeps Uzanet-owned control objects isolated, creates a pre-change backup, and aborts
on reserved-name conflicts. When HotSpot is enabled it preserves the active login page before
installing a small ISP-qualified redirect using RouterOS 6/7 shared file syntax.
"""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote, urlsplit

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


def _portal_public_origin() -> str:
    """Return the browser origin used for public customer portals.

    PORTAL_PUBLIC_URL is preferred so multi-origin production deployments are deterministic.
    Existing single-origin deployments remain compatible by falling back to the first valid
    HTTPS CORS origin.
    """
    explicit = os.getenv("PORTAL_PUBLIC_URL", "").strip().rstrip("/")
    candidates = [explicit] if explicit else list(get_settings().cors_origins)
    for candidate in candidates:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"}
        ):
            return candidate.rstrip("/")
    return ""


def _portal_identity(router: Router) -> str | None:
    return router.owner.username if router.owner else None


def _portal_redirect_html(redirect_url: str) -> str:
    """Return a self-contained transition page safe for a captive client.

    The page cannot depend on remote fonts, scripts, or animation assets because the
    client has not authenticated with the HotSpot yet. The immediate meta redirect is
    retained while the visible UI gives slow captive browsers an honest loading state
    and a manual escape hatch.
    """
    escaped_url = redirect_url.replace("&", "&amp;")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="cache-control" content="no-store">'
        f'<meta http-equiv="refresh" content="0;url={escaped_url}">'
        '<title>Connecting to Uzanet</title><style>'
        '*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;'
        'padding:24px;background:linear-gradient(145deg,#eef5ff,#f8fbff 55%,#edf9fb);'
        'color:#0b1c30;font-family:Arial,sans-serif}.card{width:min(100%,380px);padding:36px 28px;'
        'border:1px solid #dce9ff;border-radius:24px;background:rgba(255,255,255,.96);'
        'box-shadow:0 24px 64px rgba(15,42,94,.14);text-align:center}.brand{font-size:14px;'
        'font-weight:700;letter-spacing:.16em;color:#004cca;text-transform:uppercase}.signal{position:relative;'
        'width:112px;height:96px;margin:22px auto 12px}.signal span{position:absolute;left:50%;bottom:16px;'
        'border:6px solid #1677ff;border-color:#1677ff transparent transparent transparent;'
        'border-radius:50%;transform:translateX(-50%) rotate(45deg);animation:pulse 1.6s ease-in-out infinite}'
        '.signal span:nth-child(1){width:86px;height:86px}.signal span:nth-child(2){width:58px;height:58px;'
        'animation-delay:.16s}.signal span:nth-child(3){width:30px;height:30px;animation-delay:.32s}'
        '.signal b{position:absolute;left:50%;bottom:9px;width:12px;height:12px;border-radius:50%;'
        'background:#004cca;transform:translateX(-50%);box-shadow:0 0 0 8px #e5eeff}h1{margin:0;'
        'font-size:24px}p{margin:10px 0 24px;color:#56647a;line-height:1.5}.button{display:block;'
        'width:100%;padding:14px 18px;border-radius:12px;background:#005ce6;color:#fff;text-decoration:none;'
        'font-weight:700;box-shadow:0 10px 24px rgba(0,76,202,.22)}.hint{margin:14px 0 0;font-size:12px;'
        'color:#8490a3}@keyframes pulse{0%,100%{opacity:.3;transform:translateX(-50%) rotate(45deg) scale(.92)}'
        '50%{opacity:1;transform:translateX(-50%) rotate(45deg) scale(1)}}'
        '@media(prefers-reduced-motion:reduce){.signal span{animation:none}}</style></head><body>'
        '<main class="card" role="status" aria-live="polite"><div class="brand">Uzanet Wi-Fi</div>'
        '<div class="signal" aria-hidden="true"><span></span><span></span><span></span><b></b></div>'
        '<h1>Opening your internet portal</h1><p>Hold on while we load the available packages.</p>'
        f'<a class="button" href="{escaped_url}">Continue manually</a>'
        '<p class="hint">Use the button if the portal does not open automatically.</p></main></body></html>'
    )


def _fetch_compatible(command: str, arguments: str = "", variable: str = "uzanetFetch") -> str:
    """Emit a parsed fetch command using syntax shared by RouterOS 6 and 7.

    The onboarding endpoints do not redirect, so avoid newer redirect-only options.
    RouterOS 6.49 can parse a command string containing ``http-max-redirect-count``
    but then fail when the parsed command executes, bypassing an on-error fallback.
    """
    compatible = _ros_quote(command)
    return f':local {variable} [:parse "{compatible}"]; ${variable}{arguments}'


def _build_script(
    router: Router,
    claim_token: str,
    api_password: str,
    l2tp_password: str,
    replace_managed_tunnel: bool = False,
    isp_identifier: str | None = None,
) -> str:
    settings = get_settings()
    isp_identifier = isp_identifier or _portal_identity(router)
    portal_origin = _portal_public_origin()
    portal_html = ""
    if portal_origin and isp_identifier and router.portal_enabled:
        portal_url = (
            f"{portal_origin}/portal/{quote(isp_identifier, safe='')}/"
            f"{quote(router.portal_slug, safe='')}"
        )
        redirect_url = (
            f"{portal_url}?link-login-only=$(link-login-only-esc)"
            "&link-orig=$(link-orig-esc)&mac=$(mac-esc)&ip=$(ip-esc)"
        )
        portal_html = _portal_redirect_html(redirect_url)

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
        "portal_html": _ros_quote(portal_html),
    }
    claim_fetch = _fetch_compatible(
        f'/tool fetch url="{values["claim_url"]}" check-certificate=yes '
        'http-method=post http-header-field="Content-Type: application/json" '
        'http-data=$body keep-result=no',
        ' body=$claimBody',
    )

    hotspot_block = ""
    if values["portal_html"]:
        hotspot_block = rf'''
# Preserve the active HotSpot login page once, then replace only login.html with
# a small ISP-qualified redirect. This avoids /file copy and other RouterOS 7-only
# file operations while leaving all other HotSpot assets untouched.
:local portalSynced false
:local hotspotServers [/ip hotspot find where disabled=no]
:if ([:len $hotspotServers] > 0) do={{
  :foreach hotspotId in=$hotspotServers do={{
    :local profileName [/ip hotspot get $hotspotId profile]
    :local profileId [/ip hotspot profile find where name=$profileName]
    :if ([:len $profileId] = 1) do={{
      :local baseDir [/ip hotspot profile get $profileId html-directory]
      :if ([:len $baseDir] = 0) do={{ :set baseDir "hotspot" }}
      :local sourceDir $baseDir
      :local overrideDir ""
      :do {{ :set overrideDir [/ip hotspot profile get $profileId html-directory-override] }} on-error={{}}
      :if ([:len $overrideDir] > 0) do={{ :set sourceDir $overrideDir }}
      :local loginPath ($sourceDir . "/login.html")
      :local loginId [/file find where name=$loginPath]
      :if ([:len $loginId] = 1) do={{
        :local backupBase ($sourceDir . "/login-pre-uzanet")
        :local backupPath ($backupBase . ".txt")
        :local backupReady true
        :if ([:len [/file find where name=$backupPath]] = 0) do={{
          :local currentLogin [/file get $loginId contents]
          :do {{ /file print file=$backupBase }} on-error={{ :set backupReady false }}
          :delay 1s
          :local backupId [/file find where name=$backupPath]
          :if ([:len $backupId] = 1) do={{
            :do {{ /file set $backupId contents=$currentLogin }} on-error={{ :set backupReady false }}
          }} else={{ :set backupReady false }}
        }}
        :if ($backupReady) do={{
          :do {{ /file set $loginId contents="{values['portal_html']}" }} on-error={{ :set backupReady false }}
        }}
        :if ($backupReady) do={{ :set portalSynced true }}
      }}
    }}
  }}
  :if (!$portalSynced) do={{ :log warning "Uzanet portal redirect was not changed; existing HotSpot login remains active" }}
}}
'''

    return rf'''# Uzanet managed onboarding — scoped token, expires automatically
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
  /interface l2tp-client set $existingTunnel connect-to="{values['host']}" user="{values['l2tp_user']}" password="{values['l2tp_password']}" profile=default allow=chap use-ipsec=no add-default-route=no use-peer-dns=no disabled=no
}} else={{
  /interface l2tp-client add name=$tunnelName comment=$managedComment connect-to="{values['host']}" user="{values['l2tp_user']}" password="{values['l2tp_password']}" profile=default allow=chap use-ipsec=no add-default-route=no use-peer-dns=no disabled=no
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
{hotspot_block}
:local tunnelAddress ""
:for attempt from=1 to=12 do={{
  :if ([:len $tunnelAddress] = 0) do={{
    :local addrId [/ip address find where interface=$tunnelName]
    :if ([:len $addrId] = 1) do={{
      :local candidate [/ip address get $addrId address]
      :local candidateIP [:pick $candidate 0 [:find $candidate "/"]]
      :if (("{values['expected_ip']}" = "") || ($candidateIP = "{values['expected_ip']}")) do={{ :set tunnelAddress $candidate }}
    }}
    :if ([:len $tunnelAddress] = 0) do={{ :delay 5s }}
  }}
}}
:if ([:len $tunnelAddress] = 0) do={{ :error "Uzanet tunnel did not receive an address" }}

:local rosVersion [/system resource get version]
:local claimBody ("{{\"token\":\"{values['token']}\",\"tunnel_ip\":\"" . $tunnelAddress . "\",\"routeros_version\":\"" . $rosVersion . "\"}}")
{claim_fetch}
:put "Uzanet registration accepted. Check connection status in the portal."
'''


def _tls_preflight_command() -> str:
    settings = get_settings()
    return f'/tool fetch url="{settings.api_public_url}/health/live" check-certificate=yes keep-result=no'


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
        script = _build_script(
            router,
            claim_token,
            api_password,
            l2tp_password,
            body.replace_managed_tunnel,
            current_user.username,
        )
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
            "tls_preflight_command": _tls_preflight_command(),
            "legacy_ca_common_name": "ISRG Root X1",
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
    # One scoped line. Remove only a stale file before fetching, retain a freshly
    # downloaded RSC when import fails, and delete it only after successful setup.
    filename = _ros_quote(f"uzanet-{router_uid}.rsc")
    command = _ros_quote(
        f'/tool fetch url="{_ros_quote(url)}" '
        f'http-header-field="X-Onboarding-Token: {token}" '
        'check-certificate=yes dst-path=$path'
    )
    return (
        f'{{:local p "{filename}";:do {{/file remove [/file find where name=$p]}} on-error={{}};'
        f':local c "{command}";:local f [:parse $c];:local e false;'
        ':do {$f path=$p} on-error={:set e true};'
        ':if ($e) do={:error "Download failed; check connection, clock and CA trust"};'
        ':do {/import file-name=$p} on-error={:set e true};'
        ':if ($e) do={:error "Setup failed; downloaded RSC was kept for retry"};'
        ':do {/file remove [/file find where name=$p]} on-error={}}'
    )


def consume_onboarding_script(router_uid: str, token: str) -> str:
    """Return a scoped RSC while its pending onboarding capability remains valid.

    Downloads are intentionally retryable until claim or expiry. This prevents a
    successful HTTP response followed by a RouterOS/file/import failure from burning
    the only copy of the onboarding script.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(status_code=404, detail="Onboarding download is unavailable")
    db = SessionLocal()
    try:
        router = db.query(Router).filter(
            Router.uid == router_uid,
            Router.onboarding_download_hash == hash_token(token),
            Router.onboarding_token_expires_at > datetime.utcnow(),
            Router.onboarding_status == "pending",
            Router.onboarding_script_encrypted.isnot(None),
            Router.owner_id.in_(db.query(AdminUser.id).filter(AdminUser.is_active.is_(True))),
        ).first()
        if router is None:
            raise HTTPException(status_code=404, detail="Onboarding download is unavailable")
        return decrypt_secret(router.onboarding_script_encrypted)
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
    isp_identifier = _portal_identity(router)
    portal_path = (
        f"/portal/{quote(isp_identifier, safe='')}/{quote(router.portal_slug, safe='')}"
        if isp_identifier
        else f"/portal/{quote(router.portal_slug, safe='')}"
    )
    return {
        "uid": router.uid,
        "name": router.name,
        "ip_address": router.ip_address,
        "port": router.port,
        "username": router.username,
        "isp_identifier": isp_identifier,
        "portal_slug": router.portal_slug,
        "portal_path": portal_path,
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
