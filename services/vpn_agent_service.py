"""Authenticated client for the host-side xl2tpd peer provisioning agent."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import time

from fastapi import HTTPException

from settings import get_settings


MAX_RESPONSE_BYTES = 16_384


def vpn_agent_enabled() -> bool:
    settings = get_settings()
    return bool(settings.vpn_agent_socket and settings.vpn_agent_shared_secret)


def _signature(message: dict, shared_secret: str) -> str:
    canonical = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(shared_secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def _request(action: str, payload: dict) -> dict:
    settings = get_settings()
    if not vpn_agent_enabled():
        raise HTTPException(status_code=503, detail="VPN provisioning agent is not configured")

    message = {
        "action": action,
        "nonce": secrets.token_hex(16),
        "payload": payload,
        "timestamp": int(time.time()),
    }
    envelope = {**message, "signature": _signature(message, settings.vpn_agent_shared_secret)}
    wire = json.dumps(envelope, separators=(",", ":")).encode("utf-8") + b"\n"

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(settings.vpn_agent_timeout_seconds)
            client.connect(settings.vpn_agent_socket)
            client.sendall(wire)
            response = bytearray()
            while len(response) <= MAX_RESPONSE_BYTES:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
                if b"\n" in chunk:
                    break
    except (OSError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="VPN provisioning agent is unavailable") from exc

    if not response or len(response) > MAX_RESPONSE_BYTES:
        raise HTTPException(status_code=502, detail="VPN provisioning agent returned an invalid response")
    try:
        result = json.loads(bytes(response).split(b"\n", 1)[0])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="VPN provisioning agent returned invalid JSON") from exc
    if not result.get("ok"):
        code = 409 if result.get("code") in {"duplicate", "pool_exhausted"} else 502
        raise HTTPException(status_code=code, detail=str(result.get("error") or "VPN provisioning failed"))
    return result.get("result") or {}


def provision_l2tp_peer(username: str, password: str) -> str:
    result = _request("create", {"username": username, "password": password})
    address = str(result.get("ip_address") or "")
    if not address:
        raise HTTPException(status_code=502, detail="VPN provisioning agent did not assign an address")
    return address


def revoke_l2tp_peer(username: str) -> bool:
    result = _request("delete", {"username": username})
    return bool(result.get("deleted"))
