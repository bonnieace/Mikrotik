"""Hotspot and PPPoE customer lifecycle with RouterOS/DB consistency guards."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import HotspotUser, Package, PaymentSession, PPPUser, Router
from database.session import SessionLocal
from schemas import HotspotUserCreateRequest, PPPUserCreateRequest
from security import decrypt_secret, encrypt_secret
from services.mikrotik_service import (
    delete_hotspot_access,
    delete_pppoe_access,
    provision_hotspot_access,
    provision_pppoe_access,
    set_hotspot_enabled,
    set_pppoe_enabled,
)


def _package_for_router(db, package_uid: str, router: Router, service_type: str) -> Package:
    package = crud.get_package_by_uid(db, package_uid)
    if package is None or package.router_id != router.id:
        raise HTTPException(status_code=404, detail="Package not found")
    if package.service_type != service_type:
        raise HTTPException(status_code=422, detail=f"Package is not a {service_type} package")
    if not package.is_active:
        raise HTTPException(status_code=409, detail="Package is inactive")
    return package


def _new_username(prefix: str, public_id: str | None = None) -> str:
    suffix = (public_id or secrets.token_hex(8)).replace("-", "")[:12]
    return f"{prefix}{suffix}"


def _new_password() -> str:
    return secrets.token_urlsafe(12)


def serialize_hotspot_user(row: HotspotUser) -> dict:
    return {
        "uid": row.uid,
        "username": row.otp,
        "phone_number": row.phone_number,
        "is_active": row.is_active,
        "expires_at": row.expires_at,
        "package_id": row.package_id,
        "created_at": row.created_at,
    }


def serialize_pppoe_user(row: PPPUser) -> dict:
    return {
        "uid": row.uid,
        "name": row.name,
        "email": row.email,
        "pppoe_username": row.pppoe_username,
        "mobile_number": row.mobile_number,
        "location": row.location,
        "apartment": row.apartment,
        "profile": row.profile,
        "is_active": row.is_active,
        "expires_on": row.expires_on,
        "package_id": row.package_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_hotspot_users(router: Router) -> list[dict]:
    db = SessionLocal()
    try:
        return [serialize_hotspot_user(row) for row in crud.get_hotspot_users(db, router.id)]
    finally:
        db.close()


def list_pppoe_users(router: Router) -> list[dict]:
    db = SessionLocal()
    try:
        return [serialize_pppoe_user(row) for row in crud.get_ppp_users(db, router.id)]
    finally:
        db.close()


def create_hotspot_customer(router: Router, body: HotspotUserCreateRequest) -> dict:
    db = SessionLocal()
    username = body.username or _new_username("hs-")
    password = body.password or _new_password()
    try:
        package = _package_for_router(db, body.package_uid, router, "hotspot")
        expires_at = datetime.utcnow() + timedelta(minutes=package.validity_minutes)
        row = HotspotUser(
            phone_number=body.phone_number,
            amount=package.price,
            otp=username,
            password_encrypted=encrypt_secret(password),
            expires_at=expires_at,
            package_id=package.id,
            router_id=router.id,
            is_active=True,
        )
        db.add(row)
        db.flush()
        provision_hotspot_access(
            router.id,
            username,
            password,
            package.router_profile,
            package.validity_minutes,
            replace_existing=False,
        )
        crud.create_log(db, "Hotspot customer created", router_id=router.id, event_type="hotspot.created")
        db.commit()
        db.refresh(row)
        return {**serialize_hotspot_user(row), "credentials": {"username": username, "password": password}}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Hotspot username already exists") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_pppoe_customer(router: Router, body: PPPUserCreateRequest) -> dict:
    db = SessionLocal()
    try:
        package = _package_for_router(db, body.package_uid, router, "pppoe")
        expires_on = datetime.utcnow() + timedelta(minutes=package.validity_minutes)
        row = PPPUser(
            name=body.name,
            email=body.email,
            pppoe_username=body.pppoe_username,
            pppoe_password=encrypt_secret(body.pppoe_password),
            mobile_number=body.mobile_number,
            location=body.location,
            apartment=body.apartment,
            profile=package.router_profile,
            expires_on=expires_on,
            package_id=package.id,
            router_id=router.id,
            is_active=True,
        )
        db.add(row)
        db.flush()
        provision_pppoe_access(
            router.id,
            body.pppoe_username,
            body.pppoe_password,
            package.router_profile,
            replace_existing=False,
        )
        crud.create_log(db, "PPPoE customer created", router_id=router.id, event_type="pppoe.created")
        db.commit()
        db.refresh(row)
        return serialize_pppoe_user(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="PPPoE username already exists on this router") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_customer_enabled(router: Router, service_type: str, user_uid: str, enabled: bool) -> dict:
    db = SessionLocal()
    try:
        if service_type == "hotspot":
            row = crud.get_hotspot_user_by_uid(db, user_uid)
            if row is None or row.router_id != router.id:
                raise HTTPException(status_code=404, detail="Hotspot customer not found")
            set_hotspot_enabled(router.id, row.otp, enabled)
            row.is_active = enabled
            result = serialize_hotspot_user(row)
        else:
            row = crud.get_ppp_user_by_uid(db, user_uid)
            if row is None or row.router_id != router.id:
                raise HTTPException(status_code=404, detail="PPPoE customer not found")
            set_pppoe_enabled(router.id, row.pppoe_username, enabled)
            row.is_active = enabled
            result = serialize_pppoe_user(row)
        crud.create_log(
            db,
            f"{service_type} customer {'enabled' if enabled else 'disabled'}",
            router_id=router.id,
            event_type=f"{service_type}.{'enabled' if enabled else 'disabled'}",
        )
        db.commit()
        return result | {"is_active": enabled}
    finally:
        db.close()


def delete_customer(router: Router, service_type: str, user_uid: str) -> None:
    db = SessionLocal()
    try:
        if service_type == "hotspot":
            row = crud.get_hotspot_user_by_uid(db, user_uid)
            if row is None or row.router_id != router.id:
                raise HTTPException(status_code=404, detail="Hotspot customer not found")
            delete_hotspot_access(router.id, row.otp)
        else:
            row = crud.get_ppp_user_by_uid(db, user_uid)
            if row is None or row.router_id != router.id:
                raise HTTPException(status_code=404, detail="PPPoE customer not found")
            delete_pppoe_access(router.id, row.pppoe_username)
        db.delete(row)
        crud.create_log(db, f"{service_type} customer deleted", router_id=router.id, event_type=f"{service_type}.deleted")
        db.commit()
    finally:
        db.close()


def _payment_credentials(db, payment_session: PaymentSession, package: Package) -> tuple[str, str]:
    if payment_session.access_username and payment_session.access_password_encrypted:
        return payment_session.access_username, decrypt_secret(payment_session.access_password_encrypted)

    username = _new_username("hs-" if package.service_type == "hotspot" else "", payment_session.public_id)
    password = _new_password()
    payment_session.access_username = username
    payment_session.access_password_encrypted = encrypt_secret(password)
    payment_session.credentials_expires_at = datetime.utcnow() + timedelta(minutes=30)
    db.flush()
    return username, password


def prepare_paid_hotspot_session(db, payment_session: PaymentSession, package: Package) -> tuple[str, str]:
    """Prepare a disabled paid HotSpot account without granting unpaid access."""
    if package.service_type != "hotspot":
        raise HTTPException(status_code=422, detail="Only HotSpot sessions can be prepared before payment")

    username, password = _payment_credentials(db, payment_session, package)
    provision_hotspot_access(
        payment_session.router_id,
        username,
        password,
        package.router_profile,
        package.validity_minutes,
        enabled=False,
    )
    user = (
        db.query(HotspotUser)
        .filter(HotspotUser.router_id == payment_session.router_id, HotspotUser.otp == username)
        .first()
    )
    if user is None:
        user = HotspotUser(
            phone_number=payment_session.phone_number,
            amount=payment_session.amount,
            otp=username,
            password_encrypted=encrypt_secret(password),
            expires_at=None,
            router_id=payment_session.router_id,
            package_id=package.id,
            is_active=False,
        )
        db.add(user)
    else:
        user.phone_number = payment_session.phone_number
        user.amount = payment_session.amount
        user.password_encrypted = encrypt_secret(password)
        user.package_id = package.id
        user.is_active = False
        user.expires_at = None
    db.flush()
    return str(user.id), password


def cleanup_prepared_hotspot_session(db, payment_session: PaymentSession) -> bool:
    """Remove one unpaid prepared HotSpot account. Returns True when a row was cleaned."""
    if payment_session.service_type != "hotspot" or not payment_session.access_username:
        return False
    user = (
        db.query(HotspotUser)
        .filter(
            HotspotUser.router_id == payment_session.router_id,
            HotspotUser.otp == payment_session.access_username,
            HotspotUser.expires_at.is_(None),
        )
        .first()
    )
    if user is None:
        return False
    delete_hotspot_access(payment_session.router_id, payment_session.access_username)
    db.delete(user)
    payment_session.access_password_encrypted = None
    payment_session.credentials_expires_at = None
    db.flush()
    return True


def cleanup_failed_prepared_hotspot_sessions(limit: int = 200) -> dict:
    """Best-effort cleanup for failed/expired payments that prepared disabled access."""
    discovery_db = SessionLocal()
    try:
        public_ids = [
            row.public_id
            for row in (
                discovery_db.query(PaymentSession)
                .filter(
                    PaymentSession.status == "failed",
                    PaymentSession.service_type == "hotspot",
                    PaymentSession.access_username.isnot(None),
                    PaymentSession.access_password_encrypted.isnot(None),
                )
                .order_by(PaymentSession.updated_at.asc())
                .limit(limit)
                .all()
            )
        ]
    finally:
        discovery_db.close()

    cleaned = 0
    failed = 0
    for public_id in public_ids:
        db = SessionLocal()
        try:
            row = crud.get_payment_session_by_public_id(db, public_id)
            if row is not None and row.status == "failed" and cleanup_prepared_hotspot_session(db, row):
                db.commit()
                cleaned += 1
        except Exception:
            db.rollback()
            failed += 1
        finally:
            db.close()
    return {"checked": len(public_ids), "cleaned": cleaned, "failed": failed}


def provision_paid_session(db, payment_session: PaymentSession, package: Package) -> tuple[str, str]:
    """Finalize paid access idempotently; prepared HotSpot users are enabled only after payment."""
    now = datetime.utcnow()

    if package.service_type == "hotspot":
        username, password = _payment_credentials(db, payment_session, package)
        user = (
            db.query(HotspotUser)
            .filter(HotspotUser.router_id == payment_session.router_id, HotspotUser.otp == username)
            .first()
        )
        provision_hotspot_access(
            payment_session.router_id,
            username,
            password,
            package.router_profile,
            package.validity_minutes,
            enabled=True,
        )
        if user is None:
            user = HotspotUser(
                phone_number=payment_session.phone_number,
                amount=payment_session.amount,
                otp=username,
                password_encrypted=encrypt_secret(password),
                router_id=payment_session.router_id,
                package_id=package.id,
                is_active=True,
            )
            db.add(user)
            db.flush()
        user.phone_number = payment_session.phone_number
        user.amount = payment_session.amount
        user.password_encrypted = encrypt_secret(password)
        user.package_id = package.id
        user.is_active = True
        if user.expires_at is None:
            user.expires_at = now + timedelta(minutes=package.validity_minutes)
        db.flush()
        return str(user.id), password

    if not payment_session.customer_reference:
        raise HTTPException(status_code=422, detail="PPPoE account reference is required")
    user = crud.get_ppp_user_by_username(db, payment_session.router_id, payment_session.customer_reference)
    if user is None:
        raise HTTPException(status_code=404, detail="PPPoE account was not found")
    password = decrypt_secret(user.pppoe_password)
    provision_pppoe_access(payment_session.router_id, user.pppoe_username, password, package.router_profile)
    user.profile = package.router_profile
    user.package_id = package.id
    user.is_active = True
    user.expires_on = max(user.expires_on or now, now) + timedelta(minutes=package.validity_minutes)
    payment_session.access_username = user.pppoe_username
    payment_session.access_password_encrypted = None
    payment_session.credentials_expires_at = None
    db.flush()
    return str(user.id), ""
