"""Service functions for fetching currently active/online users from MikroTik routers."""

from typing import List

from fastapi import HTTPException
from services.mikrotik_service import router_api


def get_hotspot_active_users(router_id: int) -> List[dict]:
    """
    Fetch currently active hotspot sessions from the router identified by router_id.

    Args:
        router_id: Primary key of the router record in the database.

    Returns:
        List of active session dicts containing user/login name, IP address,
        MAC address, uptime, and session metadata.
    """
    try:
        with router_api(router_id) as api:
            sessions = list(api.path("ip", "hotspot", "active"))
        return [
            {
                "user": session.get("user", ""),
                "address": session.get("address", ""),
                "mac_address": session.get("mac-address", ""),
                "uptime": session.get("uptime", ""),
                "session_id": session.get(".id", ""),
                "login_by": session.get("login-by", ""),
                "server": session.get("server", ""),
            }
            for session in sessions
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Router returned an invalid hotspot response") from exc


def get_ppp_active_users(router_id: int) -> List[dict]:
    """
    Fetch currently active PPP/PPPoE sessions from the router identified by router_id.

    Args:
        router_id: Primary key of the router record in the database.

    Returns:
        List of active PPP session dicts containing username, IP address,
        caller ID, uptime, and session metadata.
    """
    try:
        with router_api(router_id) as api:
            sessions = list(api.path("ppp", "active"))
        return [
            {
                "user": session.get("name", ""),
                "address": session.get("address", ""),
                "caller_id": session.get("caller-id", ""),
                "uptime": session.get("uptime", ""),
                "session_id": session.get(".id", ""),
                "service": session.get("service", ""),
                "encoding": session.get("encoding", ""),
            }
            for session in sessions
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Router returned an invalid PPPoE response") from exc
