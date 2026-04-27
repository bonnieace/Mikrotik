from database import crud
from database.session import SessionLocal
from fastapi import HTTPException


def create_router(name: str, ip_address: str, port: int, username: str, password: str):
    db = SessionLocal()
    try:
        router = crud.create_router(db, name, ip_address, port, username, password)
        crud.create_log(db, description=f"Router '{name}' ({ip_address}:{port}) created")
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
