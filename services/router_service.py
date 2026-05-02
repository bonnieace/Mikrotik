from database import crud
from database.session import SessionLocal
from fastapi import HTTPException
from typing import Optional
import socket
import time


def create_router(name: str, ip_address: str, port: int, username: str, password: str):
    db = SessionLocal()
    try:
        router = crud.create_router(db, name, ip_address, port, username, password)
        crud.create_log(db, description=f"Router '{name}' ({ip_address}:{port}) created", router_id=router.id)
        return {
            "id": router.id,
            "name": router.name,
            "ip_address": router.ip_address,
            "port": router.port,
            "username": router.username,
        }
    except Exception as e:
        crud.create_log(db, description=f"Failed to create router '{name}': {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


def get_routers():
    db = SessionLocal()
    try:
        routers = crud.get_routers(db)
        return [
            {
                "id": r.id,
                "name": r.name,
                "ip_address": r.ip_address,
                "port": r.port,
                "username": r.username,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in routers
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


def ping_routers(router_id: Optional[int] = None, timeout: float = 2.0):
    db = SessionLocal()
    try:
        routers = crud.get_routers(db)
        if router_id is not None:
            routers = [router for router in routers if router.id == router_id]
            if not routers:
                raise HTTPException(status_code=404, detail=f"Router with id {router_id} not found")

        results = []

        for router in routers:
            started_at = time.perf_counter()
            try:
                with socket.create_connection((router.ip_address, router.port), timeout=timeout):
                    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                    results.append({
                        "id": router.id,
                        "name": router.name,
                        "ip_address": router.ip_address,
                        "port": router.port,
                        "online": True,
                        "latency_ms": latency_ms,
                    })
            except OSError as exc:
                results.append({
                    "id": router.id,
                    "name": router.name,
                    "ip_address": router.ip_address,
                    "port": router.port,
                    "online": False,
                    "error": str(exc),
                })

        return {
            "total": len(results),
            "online": sum(1 for router in results if router["online"]),
            "offline": sum(1 for router in results if not router["online"]),
            "routers": results,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
