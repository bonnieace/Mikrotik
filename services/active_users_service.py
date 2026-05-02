"""Service functions for fetching currently active/online users from MikroTik routers."""

from typing import List

from fastapi import HTTPException
from librouteros import connect
from database import crud
from database.session import SessionLocal


def _connect_to_router_by_id(router_id: int):
    """Look up a router in the DB by ID and return a librouteros API connection."""
    db = SessionLocal()
    try:
        router = crud.get_router_by_id(db, router_id)
        if not router:
            raise HTTPException(status_code=404, detail=f"Router with id {router_id} not found")
        try:
            return connect(
                username=router.username,
                password=router.password,
                host=router.ip_address,
                port=router.port,
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Could not connect to router {router_id}. Check that the router is reachable and the API service is enabled.",
            )
    finally:
        db.close()


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
        api = _connect_to_router_by_id(router_id)
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
        api = _connect_to_router_by_id(router_id)
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
