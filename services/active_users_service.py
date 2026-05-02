"""Service functions for fetching currently active/online users from MikroTik routers."""

from typing import List

from fastapi import HTTPException
from services.mikrotik_service import connect_to_router


def get_hotspot_active_users() -> List[dict]:
    """
    Fetch currently active hotspot sessions from the router configured in env.

    Returns:
        List of active session dicts containing user/login name, IP address,
        MAC address, uptime, and session metadata.
    """
    try:
        api = connect_to_router()
        resource = api.path("ip", "hotspot", "active")
        sessions = list(resource)
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_ppp_active_users() -> List[dict]:
    """
    Fetch currently active PPP/PPPoE sessions from the router configured in env.

    Returns:
        List of active PPP session dicts containing username, IP address,
        caller ID, uptime, and session metadata.
    """
    try:
        api = connect_to_router()
        resource = api.path("ppp", "active")
        sessions = list(resource)
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
