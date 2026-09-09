"""Router persistence, ownership-safe serialization, and connectivity checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import AdminUser, HotspotUser, Package, PaymentSession, PPPUser, Router
from database.session import SessionLocal
from schemas import RouterCreateRequest, RouterUpdateRequest
from security import encrypt_secret, is_encrypted
from services.mikrotik_service import router_status, validate_router_destination
from services.onboarding_service import serialize_router
from services.vpn_agent_service import revoke_l2tp_peer, vpn_agent_enabled
from settings import get_settings


def get_router_for_user(router_uid: str, current_user: AdminUser, db=None) -> Router:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        router = crud.get_router_by_uid(db, router_uid)
        if router is None or router.onboarding_status == "deleted":
            raise HTTPException(status_code=404, detail="Router not found")
        if current_user.role != "superadmin" and router.owner_id != current_user.id:
            # Do not disclose whether another tenant's router exists.
            raise HTTPException(status_code=404, detail="Router not found")
        if owns_session:
            db.expunge(router)
        return router
    finally:
        if owns_session:
            db.close()


def list_routers(current_user: AdminUser) -> list[dict]:
    db = SessionLocal()
    try:
        owner_id = None if current_user.role == "superadmin" else current_user.id
        return [serialize_router(row) for row in crud.get_routers(db, owner_id)]
    finally:
        db.close()


def create_router(body: RouterCreateRequest, current_user: AdminUser) -> dict:
    if body.payment_provider not in get_settings().payment_providers:
        raise HTTPException(status_code=422, detail="Payment provider is not enabled")
    validate_router_destination(body.ip_address)
    db = SessionLocal()
    try:
        row = crud.create_router(
            db,
            name=body.name,
            ip_address=body.ip_address,
            port=body.port,
            username=body.username,
            password=encrypt_secret(body.password),
            owner_id=current_user.id,
            portal_slug=body.portal_slug,
            portal_enabled=body.portal_enabled,
            payment_provider=body.payment_provider,
            connection_mode="direct",
            onboarding_status="configured",
        )
        crud.create_log(db, "Router created", router_id=row.id, event_type="router.created")
        db.commit()
        db.refresh(row)
        return serialize_router(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Portal slug is already in use") from exc
    finally:
        db.close()


def update_router(router_uid: str, body: RouterUpdateRequest, current_user: AdminUser) -> dict:
    db = SessionLocal()
    try:
        row = get_router_for_user(router_uid, current_user, db)
        values = body.model_dump(exclude_unset=True)
        if values.get("payment_provider") and values["payment_provider"] not in get_settings().payment_providers:
            raise HTTPException(status_code=422, detail="Payment provider is not enabled")
        if "ip_address" in values:
            validate_router_destination(values["ip_address"])
        if "password" in values:
            values["password"] = encrypt_secret(values["password"])
        for key, value in values.items():
            setattr(row, key, value)
        row.onboarding_status = "configured" if row.connection_mode == "direct" else row.onboarding_status
        crud.create_log(db, "Router updated", router_id=row.id, event_type="router.updated")
        db.commit()
        db.refresh(row)
        return serialize_router(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Portal slug is already in use") from exc
    finally:
        db.close()


def delete_router(router_uid: str, current_user: AdminUser) -> None:
    """Soft-delete a router while preserving billing and audit history.

    The previous hard delete was incompatible with router-scoped foreign keys and with the
    package API, which retires packages rather than removing their rows.  Persist the local
    deletion first, then clean up the external L2TP peer so an infrastructure failure can no
    longer roll back the application state or leave a visible router with a revoked tunnel.
    """
    db = SessionLocal()
    should_revoke_peer = False
    router_id: int | None = None
    try:
        row = crud.get_router_by_uid(db, router_uid)
        if row is None:
            raise HTTPException(status_code=404, detail="Router not found")
        if current_user.role != "superadmin" and row.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Router not found")
        if row.onboarding_status == "deleted":
            return

        router_id = row.id
        should_revoke_peer = row.connection_mode == "l2tp" and vpn_agent_enabled()

        db.query(Package).filter(Package.router_id == row.id, Package.is_active.is_(True)).update(
            {Package.is_active: False}, synchronize_session=False
        )
        db.query(HotspotUser).filter(
            HotspotUser.router_id == row.id, HotspotUser.is_active.is_(True)
        ).update({HotspotUser.is_active: False}, synchronize_session=False)
        db.query(PPPUser).filter(PPPUser.router_id == row.id, PPPUser.is_active.is_(True)).update(
            {PPPUser.is_active: False}, synchronize_session=False
        )
        db.query(PaymentSession).filter(
            PaymentSession.router_id == row.id,
            PaymentSession.status.in_(("created", "pending", "provisioning")),
        ).update(
            {
                PaymentSession.status: "failed",
                PaymentSession.result_description: "Router was deleted",
            },
            synchronize_session=False,
        )

        row.portal_enabled = False
        row.portal_slug = f"deleted-{row.uid}"
        row.onboarding_status = "deleted"
        row.onboarding_download_hash = None
        row.onboarding_script_encrypted = None
        row.onboarding_token_hash = None
        row.onboarding_token_expires_at = None
        crud.create_log(db, "Router deleted", router_id=row.id, event_type="router.deleted")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Router could not be deleted safely") from exc
    finally:
        db.close()

    if should_revoke_peer:
        try:
            revoke_l2tp_peer(f"router-{router_uid}")
        except Exception:
            # The application deletion has already committed. Record cleanup failure without
            # resurrecting the router or returning a misleading failed DELETE to the client.
            cleanup_db = SessionLocal()
            try:
                crud.create_log(
                    cleanup_db,
                    "Router deleted but L2TP peer cleanup failed",
                    router_id=router_id,
                    level="error",
                    event_type="router.delete.cleanup_failed",
                )
                cleanup_db.commit()
            finally:
                cleanup_db.close()


def check_router(router_uid: str, current_user: AdminUser) -> dict:
    db = SessionLocal()
    try:
        row = get_router_for_user(router_uid, current_user, db)
        db.expunge(row)
    finally:
        db.close()
    result = {"router_uid": row.uid, "name": row.name, **router_status(row)}
    _record_status(row.id, result)
    return result


def check_all_routers(current_user: AdminUser, max_workers: int = 8) -> dict:
    db = SessionLocal()
    try:
        owner_id = None if current_user.role == "superadmin" else current_user.id
        rows = crud.get_routers(db, owner_id)
        for row in rows:
            db.expunge(row)
    finally:
        db.close()

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(rows)))) as executor:
        future_rows = {executor.submit(router_status, row): row for row in rows}
        for future in as_completed(future_rows):
            row = future_rows[future]
            status = future.result()
            result = {"router_uid": row.uid, "name": row.name, **status}
            results.append(result)
            _record_status(row.id, result)
    results.sort(key=lambda item: item["name"].lower())
    return {
        "total": len(results),
        "online": sum(item["status"] == "online" for item in results),
        "offline": sum(item["status"] != "online" for item in results),
        "routers": results,
    }


def _record_status(router_id: int, result: dict) -> None:
    db = SessionLocal()
    try:
        row = crud.get_router_by_id(db, router_id)
        if row is None or row.onboarding_status == "deleted":
            return
        if result["status"] == "online":
            row.last_seen_at = datetime.utcnow()
            row.last_error = None
            row.routeros_version = result.get("version") or row.routeros_version
        else:
            row.last_error = str(result.get("detail") or "Router is offline")[:255]
        db.commit()
    finally:
        db.close()


def encrypt_legacy_credentials() -> int:
    """One-time in-place conversion of legacy plaintext values after migrations run."""
    db = SessionLocal()
    converted = 0
    try:
        for row in db.query(Router).all():
            if row.password and not is_encrypted(row.password):
                row.password = encrypt_secret(row.password)
                converted += 1
        for row in db.query(PPPUser).all():
            if row.pppoe_password and not is_encrypted(row.pppoe_password):
                row.pppoe_password = encrypt_secret(row.pppoe_password)
                converted += 1
        if converted:
            db.commit()
        return converted
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Legacy adapters. They are retained for imports in old modules only; the public API uses
# UUID router identifiers and JSON bodies.
# ---------------------------------------------------------------------------
def get_routers(owner_id=None):
    db = SessionLocal()
    try:
        return [serialize_router(row) | {"id": row.id} for row in crud.get_routers(db, owner_id)]
    finally:
        db.close()


def ping_routers(router_id=None, allowed_ids: Iterable[int] | None = None, timeout: float = 2.0):
    db = SessionLocal()
    try:
        rows = crud.get_routers(db)
        if allowed_ids is not None:
            allowed = set(allowed_ids)
            rows = [row for row in rows if row.id in allowed]
        if router_id is not None:
            rows = [row for row in rows if row.id == router_id]
        for row in rows:
            db.expunge(row)
    finally:
        db.close()
    results = [{"id": row.id, "name": row.name, "online": router_status(row)["status"] == "online"} for row in rows]
    return {"total": len(results), "online": sum(r["online"] for r in results), "offline": sum(not r["online"] for r in results), "routers": results}
