from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from database.models import AdminUser, HotspotUser, Package, Payment, PaymentSession, Router
from security import hash_token, payment_access_token
from services import access_service, payment_service
from services.access_service import prepare_paid_hotspot_session, provision_paid_session
from services.payment_providers import MPESA_QUERY_PENDING, MPESA_QUERY_STATUS_KEY
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


def test_hotspot_user_is_prepared_active_without_releasing_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, _token = _pending_session(db, router, package)
    router_calls = []

    def fake_provision(*args, **kwargs):
        router_calls.append((args, kwargs))

    monkeypatch.setattr(access_service, "provision_hotspot_access", fake_provision)

    user_id, password = prepare_paid_hotspot_session(db, session, package)
    db.commit()

    prepared = db.query(HotspotUser).filter_by(id=int(user_id)).one()
    assert prepared.otp == session.access_username
    assert prepared.expires_at is None
    assert prepared.is_active is True
    assert len(router_calls) == 1
    assert router_calls[0][1]["enabled"] is True
    assert "credentials" not in payment_service._public_response(session)

    finalized_user_id, finalized_password = provision_paid_session(db, session, package)
    db.commit()

    db.refresh(prepared)
    assert finalized_user_id == user_id
    assert finalized_password == password
    assert prepared.expires_at is not None
    assert prepared.is_active is True
    # Payment confirmation must not perform a second RouterOS mutation.
    assert len(router_calls) == 1


def test_public_status_query_confirms_payment_and_releases_prepared_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, token = _pending_session(db, router, package)
    router_calls = []

    def fake_provision(*args, **kwargs):
        router_calls.append((args, kwargs))

    monkeypatch.setattr(access_service, "provision_hotspot_access", fake_provision)
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


def test_inflight_mpesa_query_keeps_polling_and_hides_credentials(db, monkeypatch):
    router, package = _portal(db)
    session, token = _pending_session(db, router, package)

    monkeypatch.setattr(access_service, "provision_hotspot_access", lambda *_args, **_kwargs: None)
    prepare_paid_hotspot_session(db, session, package)
    db.commit()
    session.updated_at = datetime.utcnow() - timedelta(seconds=10)
    db.commit()

    monkeypatch.setattr(
        payment_service,
        "query_mpesa_sync",
        lambda _request_id: {
            MPESA_QUERY_STATUS_KEY: MPESA_QUERY_PENDING,
            "errorCode": "500.001.1001",
            "errorMessage": "Provider wording is diagnostic only",
        },
    )

    result = get_public_payment(session.public_id, token)

    assert result["status"] == "pending"
    assert "credentials" not in result


def test_nonzero_query_result_waits_for_callback_and_keeps_prepared_access(db, monkeypatch):
    router, package = _portal(db)
    session, token = _pending_session(db, router, package)
    calls = []

    def fake_provision(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(access_service, "provision_hotspot_access", fake_provision)
    prepare_paid_hotspot_session(db, session, package)
    db.commit()
    session.updated_at = datetime.utcnow() - timedelta(seconds=10)
    db.commit()

    monkeypatch.setattr(
        payment_service,
        "query_mpesa_sync",
        lambda _request_id: {
            MPESA_QUERY_STATUS_KEY: MPESA_QUERY_PENDING,
            "ResultCode": "1032",
            "ResultDesc": "Provider wording is diagnostic only",
        },
    )

    result = get_public_payment(session.public_id, token)

    assert result["status"] == "pending"
    assert "credentials" not in result
    prepared = db.query(HotspotUser).filter_by(otp=session.access_username).one()
    assert prepared.is_active is True
    assert prepared.expires_at is None
    assert calls[0][1]["enabled"] is True


def test_legacy_disabled_prepared_user_is_enabled_once_after_confirmed_payment(db, monkeypatch):
    router, package = _portal(db)
    session, _token = _pending_session(db, router, package)
    calls = []

    monkeypatch.setattr(access_service, "provision_hotspot_access", lambda *args, **kwargs: calls.append((args, kwargs)))
    username, password = access_service._payment_credentials(db, session, package)
    legacy = HotspotUser(
        phone_number=session.phone_number,
        amount=session.amount,
        otp=username,
        password_encrypted=access_service.encrypt_secret(password),
        expires_at=None,
        router_id=router.id,
        package_id=package.id,
        is_active=False,
    )
    db.add(legacy)
    db.commit()

    user_id, returned_password = provision_paid_session(db, session, package)
    db.commit()

    db.refresh(legacy)
    assert user_id == str(legacy.id)
    assert returned_password == password
    assert legacy.is_active is True
    assert legacy.expires_at is not None
    assert len(calls) == 1
    assert calls[0][1]["enabled"] is True
