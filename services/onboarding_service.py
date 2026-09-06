"""Generate and claim one-time, idempotent RouterOS onboarding scripts.

The script touches only Uzanet-owned objects, creates a pre-change backup, and aborts when
an object with a reserved name exists without the Uzanet ownership marker.
"""

from __future__ import annotations

import ipaddress
import re
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import AdminUser, Router
from database.session import SessionLocal
from schemas import RouterOnboardingRequest
from security import encrypt_secret, hash_token, random_token
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


def _build_script(router: Router, claim_token: str, api_password: str, l2tp_password: str) -> str:
    settings = get_settings()
    values = {
        "backup": _ros_quote(f"uzanet-pre-onboard-{router.uid.split('-')[0]}"),
        "comment": MANAGED_COMMENT,
        "host": _ros_quote(settings.router_control_host),
        "cidr": _ros_quote(settings.router_control_cidr),
        "api_user": _ros_quote(router.username),
        "api_password": _ros_quote(api_password),
        "l2tp_user": _ros_quote(_l2tp_username(router.uid)),
        "l2tp_password": _ros_quote(l2tp_password),
        "claim_url": _ros_quote(f"{settings.api_public_url}/api/v1/router-onboarding/claim"),
        "token": _ros_quote(claim_token),
    }
    return f'''# Uzanet managed onboarding — one-time token, expires automatically
# This script preserves WAN/default routes and aborts on reserved-name conflicts.
:local managedComment "{values['comment']}"
:local tunnelName "uzanet-control"
:local groupName "uzanet-api"
:local apiUser "{values['api_user']}"

/system backup save name="{values['backup']}"

:local existingTunnel [/interface l2tp-client find where name=$tunnelName]
:if ([:len $existingTunnel] > 0) do={{
  :if ([/interface l2tp-client get $existingTunnel comment] != $managedComment) do={{
    :error "Uzanet onboarding stopped: conflicting l2tp-client named uzanet-control"
  }}
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
  :if ([:len $addrId] > 0) do={{ :set tunnelAddress [/ip address get $addrId address] }}
  :if ([:len $tunnelAddress] > 0) do={{ :break }}
  :delay 5s
}}
:if ([:len $tunnelAddress] = 0) do={{ :error "Uzanet tunnel did not receive an address" }}

:local rosVersion [/system resource get version]
:local claimBody ("{{\"token\":\"{values['token']}\",\"tunnel_ip\":\"" . $tunnelAddress . "\",\"routeros_version\":\"" . $rosVersion . "\"}}")
/tool fetch url="{values['claim_url']}" http-method=post http-header-field="Content-Type: application/json" http-data=$claimBody keep-result=no
:put "Uzanet onboarding completed. Router is ready for verification."
'''


def create_onboarding(body: RouterOnboardingRequest, current_user: AdminUser) -> dict:
    settings = get_settings()
    if not settings.router_control_host:
        raise HTTPException(status_code=503, detail="Router control host is not configured")
    if body.payment_provider not in settings.payment_providers:
        raise HTTPException(status_code=422, detail="Payment provider is not enabled")

    api_password = secrets.token_urlsafe(24)
    l2tp_password = secrets.token_urlsafe(24)
    claim_token = random_token()
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
        # The L2TP credential is intentionally not stored by this API. Provision the matching
        # peer in the VPN/RADIUS control plane from the one-time response.
        crud.create_log(db, "Router onboarding created", router_id=router.id, event_type="router.onboarding.created")
        db.commit()
        db.refresh(router)
        return {
            "router": serialize_router(router),
            "expires_at": router.onboarding_token_expires_at,
            "script": _build_script(router, claim_token, api_password, l2tp_password),
            "l2tp_peer": {"username": _l2tp_username(router.uid), "password": l2tp_password},
        }
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Portal slug is already in use") from exc
    finally:
        db.close()


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

        router.ip_address = _valid_claim_ip(tunnel_ip)
        router.routeros_version = re.sub(r"[^A-Za-z0-9 ._()-]", "", routeros_version or "")[:64] or None
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
