from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from database.models import AdminUser, HotspotUser, Package, Payment, PaymentSession, Router
from security import hash_token, payment_access_token
from services import access_service, payment_service
from services.access_service import prepare_paid_hotspot_session, provision_paid_session
from services.payment_service import get_public_payment


def _portal(db):
    owner = AdminUser(username="merchant", hashed_password="unused", role="isp")
    db.add(owner)
    db.flush()
    router = Router(
        name="Town WiFi",
        ip_address="10.77.0.5",
        username="api-user",
        password="encrypted-placeholder",
        owner_id=owner.id,
        portal_slug="town-wifi",
        payment_provider="mpesa",
    )
    db.add(router)
    db.flush()
    package = Package(
        name="One hour",
        price=Decimal("10.00"),
        service_type="hotspot",
        validity_minutes=60,
        validity_days=1,
        router_profile="paid-1h",
        router_id=router.id,
    )
    db.add(package)
    db.commit()
    return router, package


def _pending_session(db, router, package):
    row = PaymentSession(
        access_token_hash="pending",
        idempotency_key="api-driven-idem",
        request_fingerprint="f" * 64,
        provider="mpesa",
        provider_request_id="checkout-api-driven",
        status="pending",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(row)
    db.flush()
    token = payment_access_token(row.public_id)
    row.access_token_hash = hash_token(token)
    db.commit()
    return row, token


def test_hotspot_user_is_prepared_without_releasing_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, _token = _pending_session(db, router, package)
    router_calls = []

    monkeypatch.setattr(
        access_service,
        "provision_hotspot_access",
        lambda *args: router_calls.append(args),
    )

    user_id, password = prepare_paid_hotspot_session(db, session, package)
    db.commit()

    prepared = db.query(HotspotUser).filter_by(id=int(user_id)).one()
    assert prepared.otp == session.access_username
    assert prepared.expires_at is None
    assert len(router_calls) == 1
    assert "credentials" not in payment_service._public_response(session)

    finalized_user_id, finalized_password = provision_paid_session(db, session, package)
    db.commit()

    db.refresh(prepared)
    assert finalized_user_id == user_id
    assert finalized_password == password
    assert prepared.expires_at is not None
    # Finalization uses the already-created RouterOS user instead of recreating it.
    assert len(router_calls) == 1


def test_public_status_query_confirms_payment_and_releases_prepared_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, token = _pending_session(db, router, package)
    router_calls = []

    monkeypatch.setattr(
        access_service,
        "provision_hotspot_access",
        lambda *args: router_calls.append(args),
    )
    _user_id, password = prepare_paid_hotspot_session(db, session, package)
    db.commit()

    session.updated_at = datetime.utcnow() - timedelta(seconds=10)
    db.commit()

    queries = []

    def fake_query(request_id):
        queries.append(request_id)
        return {
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully.",
            "MpesaReceiptNumber": "TESTRECEIPT123",
        }

    monkeypatch.setattr(payment_service, "query_mpesa_sync", fake_query)

    result = get_public_payment(session.public_id, token)

    assert queries == ["checkout-api-driven"]
    assert result["status"] == "provisioned"
    assert result["credentials"]["username"] == session.access_username
    assert result["credentials"]["password"] == password
    assert len(router_calls) == 1
    assert db.query(Payment).filter_by(invoice=session.public_id).count() == 1


def test_failed_payment_never_releases_prepared_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, token = _pending_session(db, router, package)

    monkeypatch.setattr(access_service, "provision_hotspot_access", lambda *_args: None)
    prepare_paid_hotspot_session(db, session, package)
    db.commit()
    session.updated_at = datetime.utcnow() - timedelta(seconds=10)
    db.commit()

    monkeypatch.setattr(
        payment_service,
        "query_mpesa_sync",
        lambda _request_id: {"ResultCode": "1032", "ResultDesc": "Request cancelled by user"},
    )

    result = get_public_payment(session.public_id, token)

    assert result["status"] == "failed"
    assert "credentials" not in result
