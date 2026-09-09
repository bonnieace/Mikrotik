from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from database import crud
from database.models import AdminUser, HotspotUser, Log, Package, PaymentSession, PPPUser, Router
from schemas import HotspotUserCreateRequest, PPPUserCreateRequest
from security import encrypt_secret
from services import access_service, router_service
from services.router_service import delete_router, get_router_for_user


def _owner(db, username: str = "owner") -> AdminUser:
    row = AdminUser(username=username, hashed_password="unused", role="isp")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _router(db, owner: AdminUser, *, slug: str = "branch", mode: str = "l2tp") -> Router:
    row = Router(
        name="Branch",
        ip_address="10.77.0.12",
        port=8728,
        username="api-user",
        password=encrypt_secret("router-password"),
        owner_id=owner.id,
        portal_slug=slug,
        portal_enabled=True,
        payment_provider="mpesa",
        connection_mode=mode,
        onboarding_status="claimed" if mode == "l2tp" else "configured",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _package(db, router: Router, *, name: str = "One hour", service_type: str = "hotspot") -> Package:
    row = Package(
        name=name,
        price=Decimal("10.00"),
        service_type=service_type,
        validity_minutes=60,
        validity_days=1,
        router_profile="default",
        router_id=router.id,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_router_delete_is_soft_idempotent_and_releases_portal_slug(db, monkeypatch):
    owner = _owner(db)
    router = _router(db, owner, slug="reusable-branch")
    package = _package(db, router)
    hotspot = HotspotUser(
        phone_number="254712345678",
        amount=Decimal("10.00"),
        otp="hs-user",
        password_encrypted=encrypt_secret("hotspot-password"),
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        package_id=package.id,
        router_id=router.id,
    )
    ppp_package = _package(db, router, name="Monthly", service_type="pppoe")
    ppp = PPPUser(
        name="Subscriber",
        pppoe_username="subscriber",
        pppoe_password=encrypt_secret("pppoe-password"),
        mobile_number="254712345679",
        profile="default",
        package_id=ppp_package.id,
        router_id=router.id,
        is_active=True,
    )
    pending = PaymentSession(
        access_token_hash="x" * 64,
        idempotency_key="delete-test-pending",
        request_fingerprint="f" * 64,
        provider="mpesa",
        status="pending",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    paid_retry = PaymentSession(
        access_token_hash="y" * 64,
        idempotency_key="delete-test-paid",
        request_fingerprint="g" * 64,
        provider="mpesa",
        status="provisioning_failed",
        phone_number="254712345679",
        phone_hash="q" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add_all([hotspot, ppp, pending, paid_retry])
    db.commit()

    revoked = []
    monkeypatch.setattr(router_service, "vpn_agent_enabled", lambda: True)
    monkeypatch.setattr(router_service, "revoke_l2tp_peer", lambda username: revoked.append(username))

    delete_router(router.uid, owner)
    delete_router(router.uid, owner)  # DELETE remains idempotent.

    db.expire_all()
    deleted = crud.get_router_by_uid(db, router.uid)
    assert deleted is not None
    assert deleted.onboarding_status == "deleted"
    assert deleted.portal_enabled is False
    assert deleted.portal_slug == f"deleted-{router.uid}"
    assert revoked == [f"router-{router.uid}"]
    assert crud.get_routers(db, owner.id) == []
    assert all(not row.is_active for row in crud.get_packages(db, router.id))

    # Router deletion does not pretend RouterOS customer accounts were disabled.
    assert crud.get_hotspot_users(db, router.id)[0].is_active is True
    assert crud.get_ppp_users(db, router.id)[0].is_active is True
    assert crud.get_payment_session_by_public_id(db, pending.public_id).status == "failed"
    assert crud.get_payment_session_by_public_id(db, paid_retry.public_id).status == "manual_review"

    with pytest.raises(HTTPException) as exc:
        get_router_for_user(router.uid, owner)
    assert exc.value.status_code == 404

    # The old customer-facing slug can be reused immediately.
    replacement = _router(db, owner, slug="reusable-branch", mode="direct")
    assert replacement.portal_slug == "reusable-branch"


def test_router_delete_does_not_resurrect_if_vpn_cleanup_fails(db, monkeypatch):
    owner = _owner(db)
    router = _router(db, owner, slug="cleanup-failure")
    monkeypatch.setattr(router_service, "vpn_agent_enabled", lambda: True)

    def fail_cleanup(_username):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(router_service, "revoke_l2tp_peer", fail_cleanup)

    delete_router(router.uid, owner)

    db.expire_all()
    deleted = crud.get_router_by_uid(db, router.uid)
    assert deleted.onboarding_status == "deleted"
    cleanup_logs = (
        db.query(Log)
        .filter(Log.router_id == router.id, Log.event_type == "router.delete.cleanup_failed")
        .all()
    )
    assert len(cleanup_logs) == 1
    assert cleanup_logs[0].level == "error"


def test_duplicate_hotspot_db_identity_never_mutates_routeros(db, monkeypatch):
    owner = _owner(db)
    router = _router(db, owner, slug="hotspot-duplicate", mode="direct")
    package = _package(db, router)
    existing = HotspotUser(
        phone_number="254700000001",
        amount=package.price,
        otp="same-user",
        password_encrypted=encrypt_secret("existing-password"),
        package_id=package.id,
        router_id=router.id,
        is_active=True,
    )
    db.add(existing)
    db.commit()

    calls = []
    monkeypatch.setattr(access_service, "provision_hotspot_access", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(HTTPException) as exc:
        access_service.create_hotspot_customer(
            router,
            HotspotUserCreateRequest(
                phone_number="254700000002",
                username="same-user",
                password="replacement-password",
                package_uid=package.uid,
            ),
        )
    assert exc.value.status_code == 409
    assert calls == []


def test_duplicate_pppoe_db_identity_never_mutates_routeros(db, monkeypatch):
    owner = _owner(db)
    router = _router(db, owner, slug="pppoe-duplicate", mode="direct")
    package = _package(db, router, service_type="pppoe")
    existing = PPPUser(
        name="Existing",
        pppoe_username="same-pppoe",
        pppoe_password=encrypt_secret("existing-password"),
        mobile_number="254700000003",
        profile="default",
        package_id=package.id,
        router_id=router.id,
        is_active=True,
    )
    db.add(existing)
    db.commit()

    calls = []
    monkeypatch.setattr(access_service, "provision_pppoe_access", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(HTTPException) as exc:
        access_service.create_pppoe_customer(
            router,
            PPPUserCreateRequest(
                name="Replacement",
                pppoe_username="same-pppoe",
                pppoe_password="replacement-password",
                mobile_number="254700000004",
                package_uid=package.uid,
            ),
        )
    assert exc.value.status_code == 409
    assert calls == []
