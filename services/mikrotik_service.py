"""Bounded RouterOS API operations.

Every call authenticates with an encrypted database credential and uses a socket timeout.
Callers receive stable errors; raw credentials and provider responses are never included.
"""

from __future__ import annotations

import ipaddress
import socket
from contextlib import contextmanager
from datetime import timedelta

from fastapi import HTTPException
from librouteros import connect

from database import crud
from database.models import Router
from database.session import SessionLocal
from security import decrypt_secret
from settings import get_settings


def validate_router_destination(host: str) -> None:
    try:
        addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, None)}
        networks = [ipaddress.ip_network(cidr, strict=False) for cidr in get_settings().router_allowed_cidrs]
    except (socket.gaierror, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Router address is invalid or cannot be resolved") from exc
    if not addresses or not all(any(address in network for network in networks) for address in addresses):
        raise HTTPException(status_code=422, detail="Router address is outside the configured control networks")


def _load_router(router_id: int) -> Router:
    db = SessionLocal()
    try:
        router = crud.get_router_by_id(db, router_id)
        if router is None or router.onboarding_status == "deleted":
            raise HTTPException(status_code=404, detail="Router not found")
        db.expunge(router)
        return router
    finally:
        db.close()


def _close_api(api) -> None:
    try:
        if hasattr(api, "close"):
            api.close()
        elif hasattr(api, "transport") and hasattr(api.transport, "close"):
            api.transport.close()
    except Exception:
        pass


@contextmanager
def router_api(router_or_id: Router | int):
    router = _load_router(router_or_id) if isinstance(router_or_id, int) else router_or_id
    if router.onboarding_status == "deleted":
        raise HTTPException(status_code=404, detail="Router not found")
    validate_router_destination(router.ip_address)
    try:
        password = decrypt_secret(router.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Router credential must be rotated") from exc
    try:
        api = connect(
            username=router.username,
            password=password,
            host=router.ip_address,
            port=router.port,
            timeout=get_settings().router_connect_timeout_seconds,
        )
    except (OSError, socket.timeout) as exc:
        raise HTTPException(status_code=503, detail="Router is unreachable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Router authentication failed") from exc
    try:
        yield api
    finally:
        _close_api(api)


def connect_to_router(router_id: int):
    """Compatibility helper. New code should use ``router_api`` so sockets are closed."""
    router = _load_router(router_id)
    validate_router_destination(router.ip_address)
    try:
        return connect(
            username=router.username,
            password=decrypt_secret(router.password),
            host=router.ip_address,
            port=router.port,
            timeout=get_settings().router_connect_timeout_seconds,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Router connection failed") from exc


def router_status(router: Router) -> dict:
    try:
        with router_api(router) as api:
            resource = list(api.path("system", "resource"))
            info = resource[0] if resource else {}
        return {
            "status": "online",
            "authenticated": True,
            "version": info.get("version"),
            "uptime": info.get("uptime"),
            "board_name": info.get("board-name"),
        }
    except HTTPException as exc:
        return {"status": "offline", "authenticated": False, "detail": exc.detail}


def _traffic_interface(api) -> str:
    interfaces = list(api.path("interface"))
    if not interfaces:
        raise HTTPException(status_code=502, detail="Router returned no interfaces")

    named_bridge = next((row for row in interfaces if row.get("name") == "bridge"), None)
    if named_bridge:
        return "bridge"

    running_bridge = next(
        (
            row
            for row in interfaces
            if str(row.get("type", "")).lower() == "bridge"
            and str(row.get("running", "")).lower() in {"true", "yes"}
            and row.get("name")
        ),
        None,
    )
    if running_bridge:
        return str(running_bridge["name"])

    running = next(
        (
            row
            for row in interfaces
            if str(row.get("running", "")).lower() in {"true", "yes"}
            and str(row.get("type", "")).lower() != "loopback"
            and row.get("name")
        ),
        None,
    )
    if running:
        return str(running["name"])

    fallback = next((row for row in interfaces if row.get("name")), None)
    if fallback:
        return str(fallback["name"])
    raise HTTPException(status_code=502, detail="Router returned no usable interface")


def fetch_rt_rx_tx_data(router_id: int):
    with router_api(router_id) as api:
        interface = _traffic_interface(api)
        result = list(api.path("interface", "monitor-traffic")("once", interface=interface))
    if not result:
        raise HTTPException(status_code=502, detail="Router returned no traffic data")
    return {
        "interface": interface,
        "rx_bits_per_second": result[0].get("rx-bits-per-second", 0),
        "tx_bits_per_second": result[0].get("tx-bits-per-second", 0),
    }


def _upsert_router_user(
    resource,
    username: str,
    password: str,
    profile: str,
    duration: str | None,
    *,
    replace_existing: bool = True,
    enabled: bool = True,
) -> None:
    existing = [row for row in resource if row.get("name") == username]
    values = {
        "name": username,
        "password": password,
        "profile": profile,
        "disabled": "no" if enabled else "yes",
    }
    if duration:
        values["limit-uptime"] = duration
    if existing:
        if not replace_existing:
            raise HTTPException(status_code=409, detail="Username already exists on router")
        resource.update(**{**values, ".id": existing[0][".id"]})
    else:
        resource.add(**values)


def provision_hotspot_access(
    router_id: int,
    username: str,
    password: str,
    profile: str,
    minutes: int,
    *,
    replace_existing: bool = True,
    enabled: bool = True,
) -> None:
    duration = routeros_duration(minutes)
    with router_api(router_id) as api:
        _upsert_router_user(
            api.path("ip", "hotspot", "user"),
            username,
            password,
            profile,
            duration,
            replace_existing=replace_existing,
            enabled=enabled,
        )


def set_hotspot_enabled(router_id: int, username: str, enabled: bool) -> None:
    with router_api(router_id) as api:
        resource = api.path("ip", "hotspot", "user")
        rows = [row for row in resource if row.get("name") == username]
        if not rows:
            raise HTTPException(status_code=404, detail="Hotspot user not found on router")
        resource.update(**{".id": rows[0][".id"], "disabled": "no" if enabled else "yes"})


def delete_hotspot_access(router_id: int, username: str) -> None:
    with router_api(router_id) as api:
        users = api.path("ip", "hotspot", "user")
        for row in [item for item in users if item.get("name") == username]:
            users.remove(row[".id"])
        active = api.path("ip", "hotspot", "active")
        for row in [item for item in active if item.get("user") == username]:
            active.remove(row[".id"])


def provision_pppoe_access(
    router_id: int,
    username: str,
    password: str,
    profile: str,
    *,
    replace_existing: bool = True,
    enabled: bool = True,
) -> None:
    with router_api(router_id) as api:
        resource = api.path("ppp", "secret")
        existing = [row for row in resource if row.get("name") == username]
        values = {
            "name": username,
            "password": password,
            "profile": profile,
            "service": "pppoe",
            "disabled": "no" if enabled else "yes",
        }
        if existing:
            if not replace_existing:
                raise HTTPException(status_code=409, detail="Username already exists on router")
            resource.update(**{**values, ".id": existing[0][".id"]})
        else:
            resource.add(**values)


def set_pppoe_enabled(router_id: int, username: str, enabled: bool) -> None:
    with router_api(router_id) as api:
        resource = api.path("ppp", "secret")
        rows = [row for row in resource if row.get("name") == username]
        if not rows:
            raise HTTPException(status_code=404, detail="PPPoE user not found on router")
        resource.update(**{".id": rows[0][".id"], "disabled": "no" if enabled else "yes"})
        if not enabled:
            active = api.path("ppp", "active")
            for row in [item for item in active if item.get("name") == username]:
                active.remove(row[".id"])


def delete_pppoe_access(router_id: int, username: str) -> None:
    with router_api(router_id) as api:
        resource = api.path("ppp", "secret")
        for row in [item for item in resource if item.get("name") == username]:
            resource.remove(row[".id"])


def routeros_duration(minutes: int) -> str:
    delta = timedelta(minutes=minutes)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    mins = remainder // 60
    return f"{days}d{hours:02d}:{mins:02d}:00" if days else f"{hours:02d}:{mins:02d}:00"
