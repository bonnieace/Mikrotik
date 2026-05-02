"""Service functions for fetching currently active/online users from MikroTik routers."""

from datetime import datetime
from typing import List, Optional

from database import crud
from database.session import SessionLocal
from fastapi import HTTPException
from librouteros import connect


def _connect_to_db_router(router):
    """Create a librouteros API connection to a DB-stored router record."""
    try:
        api = connect(
            username=router.username,
            password=router.password,
            host=router.ip_address,
            port=router.port,
        )
        return api
    except Exception as e:
        raise Exception(
            f"Failed to connect to router '{router.name}' ({router.ip_address}): {e}"
        )


def get_hotspot_active_users(router_id: Optional[int] = None) -> List[dict]:
    """
    Fetch currently active hotspot sessions from one or all configured routers.

    Args:
        router_id: If provided, only query this specific router. Otherwise aggregate
                   across all routers stored in the database.

    Returns:
        List of active session dicts, each containing router identifier, user/login
        name, IP address, MAC address, uptime, and session metadata.
    """
    db = SessionLocal()
    try:
        routers = crud.get_routers(db)
        if router_id is not None:
            routers = [r for r in routers if r.id == router_id]
            if not routers:
                raise HTTPException(
                    status_code=404,
                    detail=f"Router with id {router_id} not found",
                )

        results = []
        for router in routers:
            try:
                api = _connect_to_db_router(router)
                resource = api.path("ip", "hotspot", "active")
                sessions = list(resource)
                for session in sessions:
                    results.append({
                        "router_id": router.id,
                        "router_name": router.name,
                        "user": session.get("user", ""),
                        "address": session.get("address", ""),
                        "mac_address": session.get("mac-address", ""),
                        "uptime": session.get("uptime", ""),
                        "session_id": session.get(".id", ""),
                        "login_by": session.get("login-by", ""),
                        "server": session.get("server", ""),
                    })
            except HTTPException:
                raise
            except Exception as e:
                # Record per-router errors so remaining routers can still be queried.
                results.append({
                    "router_id": router.id,
                    "router_name": router.name,
                    "error": str(e),
                })
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


def get_ppp_active_users(router_id: Optional[int] = None) -> List[dict]:
    """
    Fetch currently active PPP/PPPoE sessions from one or all configured routers.

    Args:
        router_id: If provided, only query this specific router. Otherwise aggregate
                   across all routers stored in the database.

    Returns:
        List of active PPP session dicts, each containing router identifier, username,
        IP address, caller ID, uptime, and session metadata.
    """
    db = SessionLocal()
    try:
        routers = crud.get_routers(db)
        if router_id is not None:
            routers = [r for r in routers if r.id == router_id]
            if not routers:
                raise HTTPException(
                    status_code=404,
                    detail=f"Router with id {router_id} not found",
                )

        results = []
        for router in routers:
            try:
                api = _connect_to_db_router(router)
                resource = api.path("ppp", "active")
                sessions = list(resource)
                for session in sessions:
                    results.append({
                        "router_id": router.id,
                        "router_name": router.name,
                        "user": session.get("name", ""),
                        "address": session.get("address", ""),
                        "caller_id": session.get("caller-id", ""),
                        "uptime": session.get("uptime", ""),
                        "session_id": session.get(".id", ""),
                        "service": session.get("service", ""),
                        "encoding": session.get("encoding", ""),
                    })
            except HTTPException:
                raise
            except Exception as e:
                # Record per-router errors so remaining routers can still be queried.
                results.append({
                    "router_id": router.id,
                    "router_name": router.name,
                    "error": str(e),
                })
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
