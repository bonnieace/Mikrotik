"""Router-scoped hotspot and PPPoE package management."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import Package, Router
from database.session import SessionLocal
from schemas import PackageCreateRequest, PackageUpdateRequest


def serialize_package(row: Package) -> dict:
    return {
        "uid": row.uid,
        "name": row.name,
        "description": row.description,
        "price": row.price,
        "service_type": row.service_type,
        "validity_minutes": row.validity_minutes,
        "router_profile": row.router_profile,
        "rate_limit": row.rate_limit,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_packages(router: Router, *, active_only: bool = False) -> list[dict]:
    db = SessionLocal()
    try:
        return [serialize_package(row) for row in crud.get_packages(db, router.id, active_only)]
    finally:
        db.close()

def create_package(router: Router, body: PackageCreateRequest) -> dict:
    db = SessionLocal()
    try:
        values = body.model_dump()
        values["validity_days"] = max(1, (values["validity_minutes"] + 1439) // 1440)
        row = crud.create_package(db, router_id=router.id, **values)
        crud.create_log(db, "Package created", router_id=router.id, event_type="package.created")
        db.commit()
        db.refresh(row)
        return serialize_package(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A package with this name already exists") from exc
    finally:
        db.close()


def update_package(router: Router, package_uid: str, body: PackageUpdateRequest) -> dict:
    db = SessionLocal()
    try:
        row = crud.get_package_by_uid(db, package_uid)
        if row is None or row.router_id != router.id:
            raise HTTPException(status_code=404, detail="Package not found")
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        if body.validity_minutes is not None:
            row.validity_days = max(1, (body.validity_minutes + 1439) // 1440)
        crud.create_log(db, "Package updated", router_id=router.id, event_type="package.updated")
        db.commit()
        db.refresh(row)
        return serialize_package(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A package with this name already exists") from exc
    finally:
        db.close()


def retire_package(router: Router, package_uid: str) -> dict:
    return update_package(router, package_uid, PackageUpdateRequest(is_active=False))


# Compatibility wrappers used by older modules.
def get_packages(router_id=None):
    db = SessionLocal()
    try:
        return [serialize_package(row) | {"id": row.id, "router_id": row.router_id} for row in crud.get_packages(db, router_id)]
    finally:
        db.close()
