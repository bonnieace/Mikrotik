"""Small, transaction-neutral SQLAlchemy data-access helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .models import AdminUser, HotspotUser, Log, Package, Payment, PaymentSession, PPPUser, Router


def calculate_expires_at(created_at: datetime, amount: int) -> datetime | None:
    minutes = {1: 60, 10: 60, 50: 1440, 150: 4320, 300: 10080, 1000: 40320}.get(int(amount))
    return created_at + timedelta(minutes=minutes) if minutes else None


def create_hotspot_user(db: Session, phone_number: str, amount: float, otp: str, router_id: int = None):
    row = HotspotUser(
        phone_number=phone_number,
        amount=amount,
        otp=otp,
        expires_at=calculate_expires_at(datetime.utcnow(), amount),
        router_id=router_id,
    )
    db.add(row)
    db.flush()
    return row


def create_ppp_user(db: Session, name, email, pppoe_username, pppoe_password, mobile_number, location, apartment, profile, router_id=None):
    from security import encrypt_secret

    row = PPPUser(
        name=name,
        email=email,
        pppoe_username=pppoe_username,
        pppoe_password=encrypt_secret(pppoe_password),
        mobile_number=mobile_number,
        location=location,
        apartment=apartment,
        profile=profile,
        router_id=router_id,
    )
    db.add(row)
    db.flush()
    return row


def create_payment(db: Session, invoice: str, amount: float, user_type: str, user_id: int, router_id: int = None):
    row = Payment(invoice=invoice, amount=amount, user_type=user_type, user_id=user_id, router_id=router_id)
    db.add(row)
    db.flush()
    return row


def create_log(
    db: Session,
    description: str,
    phone_number: str | None = None,
    router_id: int | None = None,
    *,
    level: str = "info",
    event_type: str | None = None,
) -> Log:
    row = Log(
        description=description,
        phone_number=phone_number,
        router_id=router_id,
        level=level,
        event_type=event_type,
    )
    db.add(row)
    db.flush()
    return row


def get_logs(db: Session, router_id: int | None = None):
    query = db.query(Log)
    if router_id is not None:
        query = query.filter(Log.router_id == router_id)
    return query.order_by(Log.timestamp.desc()).all()


def create_admin_user(db: Session, username: str, hashed_password: str, role: str = "isp", email: str = None):
    row = AdminUser(username=username, email=email, hashed_password=hashed_password, role=role)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_admin_user_by_username(db: Session, username: str):
    return db.query(AdminUser).filter(AdminUser.username == username).first()


def get_admin_user_by_id(db: Session, user_id: int):
    return db.query(AdminUser).filter(AdminUser.id == user_id).first()


def list_admin_users(db: Session):
    return db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()


def create_router(db: Session, **values) -> Router:
    row = Router(**values)
    db.add(row)
    db.flush()
    return row


def get_routers(db: Session, owner_id: Optional[int] = None, *, include_deleted: bool = False):
    query = db.query(Router)
    if not include_deleted:
        query = query.filter(Router.onboarding_status != "deleted")
    if owner_id is not None:
        query = query.filter(Router.owner_id == owner_id)
    return query.order_by(Router.created_at.desc()).all()


def get_router_by_id(db: Session, router_id: int):
    return db.query(Router).filter(Router.id == router_id).first()


def get_router_by_uid(db: Session, router_uid: str):
    return db.query(Router).filter(Router.uid == router_uid).first()


def get_router_by_portal_slug(db: Session, portal_slug: str):
    return db.query(Router).filter(Router.portal_slug == portal_slug).first()


def update_router(db: Session, router_id: int, **values):
    row = get_router_by_id(db, router_id)
    if row is None:
        return None
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)
    db.flush()
    return row


def delete_router(db: Session, router_id: int) -> bool:
    row = get_router_by_id(db, router_id)
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def create_package(db: Session, **values) -> Package:
    row = Package(**values)
    db.add(row)
    db.flush()
    return row


def get_packages(db: Session, router_id: int | None = None, active_only: bool = False):
    query = db.query(Package)
    if router_id is not None:
        query = query.filter(Package.router_id == router_id)
    if active_only:
        query = query.filter(Package.is_active.is_(True))
    return query.order_by(Package.price.asc()).all()


def get_package_by_uid(db: Session, package_uid: str):
    return db.query(Package).filter(Package.uid == package_uid).first()


def get_hotspot_users(db: Session, router_id: int | None = None):
    query = db.query(HotspotUser)
    if router_id is not None:
        query = query.filter(HotspotUser.router_id == router_id)
    return query.order_by(HotspotUser.created_at.desc()).all()


def get_hotspot_user_by_uid(db: Session, uid: str):
    return db.query(HotspotUser).filter(HotspotUser.uid == uid).first()


def get_ppp_users(db: Session, router_id: int | None = None):
    query = db.query(PPPUser)
    if router_id is not None:
        query = query.filter(PPPUser.router_id == router_id)
    return query.order_by(PPPUser.created_at.desc()).all()


def get_ppp_user_by_uid(db: Session, uid: str):
    return db.query(PPPUser).filter(PPPUser.uid == uid).first()


def get_ppp_user_by_username(db: Session, router_id: int, username: str):
    return (
        db.query(PPPUser)
        .filter(PPPUser.router_id == router_id, PPPUser.pppoe_username == username)
        .first()
    )


def get_payments(db: Session, router_id: int | None = None):
    query = db.query(Payment)
    if router_id is not None:
        query = query.filter(Payment.router_id == router_id)
    return query.order_by(Payment.created_at.desc()).all()


def get_payments_by_user_type(db: Session, user_type: str, router_id: int | None = None):
    query = db.query(Payment).filter(Payment.user_type == user_type)
    if router_id is not None:
        query = query.filter(Payment.router_id == router_id)
    return query.order_by(Payment.created_at.desc()).all()


def get_payment_totals_for_today_by_user_type(db: Session, user_type: str, router_id: int | None = None):
    start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    rows = get_payments_by_user_type(db, user_type, router_id)
    return sum((row.amount for row in rows if row.created_at >= start), 0)


def recent_payment_session_count(db: Session, phone_hash: str, client_ip_hash: str | None, minutes: int) -> int:
    since = datetime.utcnow() - timedelta(minutes=minutes)
    query = db.query(PaymentSession).filter(
        PaymentSession.created_at >= since,
        PaymentSession.phone_hash == phone_hash,
    )
    if client_ip_hash:
        query = query.filter(PaymentSession.client_ip_hash == client_ip_hash)
    return query.count()


def get_payment_session_by_public_id(db: Session, public_id: str):
    return db.query(PaymentSession).filter(PaymentSession.public_id == public_id).first()


def get_payment_session_by_provider_id(db: Session, provider_request_id: str):
    return db.query(PaymentSession).filter(PaymentSession.provider_request_id == provider_request_id).first()


def get_payment_session_by_idempotency(db: Session, router_id: int, idempotency_key: str):
    return (
        db.query(PaymentSession)
        .filter(PaymentSession.router_id == router_id, PaymentSession.idempotency_key == idempotency_key)
        .first()
    )


def get_payment_sessions(db: Session, router_id: int, limit: int = 200):
    return (
        db.query(PaymentSession)
        .filter(PaymentSession.router_id == router_id)
        .order_by(PaymentSession.created_at.desc())
        .limit(limit)
        .all()
    )
