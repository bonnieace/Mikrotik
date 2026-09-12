from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from fastapi import HTTPException

from database.models import AdminUser, Package, Payment, PaymentSession, Router
from schemas import PublicPaymentRequest
from services import payment_service
from services.payment_providers import (
    MPESA_QUERY_PENDING,
    MPESA_QUERY_RETRYABLE_ERROR,
    MPESA_QUERY_STATUS_KEY,
    MPESA_QUERY_SUCCEEDED,
    ProviderInitiation,
    _mpesa_query_response,
    verify_kopokopo_signature,
)
from services.payment_service import (
    complete_payment,
    create_public_payment,
    get_public_payment,
    list_payment_sessions,
    process_mpesa_callback,
)


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


@pytest.mark.asyncio
async def test_public_payment_uses_server_price_and_is_idempotent(db, monkeypatch):
    _router, package = _portal(db)
    calls = []

    async def fake_initiate(provider, phone, amount, public_id):
        calls.append((provider, phone, amount, public_id))
        return ProviderInitiation(request_id="checkout-123", customer_message="Approve on phone")

    monkeypatch.setattr(payment_service, "initiate_provider", fake_initiate)
    body = PublicPaymentRequest(package_uid=package.uid, phone_number="0712345678")
    first = await create_public_payment("town-wifi", body, "idem-key-123", "127.0.0.1")
    second = await create_public_payment("town-wifi", body, "idem-key-123", "127.0.0.1")

    assert first["payment_id"] == second["payment_id"]
    assert first["amount"] == Decimal("10.00")
    assert len(calls) == 1
    assert calls[0][2] == Decimal("10.00")
    assert get_public_payment(first["payment_id"], first["status_token"])["status"] == "pending"
    with pytest.raises(HTTPException) as exc:
        get_public_payment(first["payment_id"], "wrong-token")
    assert exc.value.status_code == 404

    stored = db.query(PaymentSession).filter(PaymentSession.public_id == first["payment_id"]).first()
    assert stored.access_token_hash != first["status_token"]
    admin_rows = list_payment_sessions(_router)
    assert admin_rows[0]["phone_number"] == "254****678"
    assert "status_token" not in admin_rows[0]


def test_mpesa_query_error_code_is_retryable_without_message_matching():
    response = httpx.Response(
        500,
        json={
            "errorCode": "500.001.1001",
            "errorMessage": "Provider wording can change without changing our state machine",
        },
    )

    result = _mpesa_query_response(response)

    assert result[MPESA_QUERY_STATUS_KEY] == MPESA_QUERY_RETRYABLE_ERROR
    assert result["errorCode"] == "500.001.1001"


def test_mpesa_nonzero_query_result_is_pending_without_message_matching():
    response = httpx.Response(
        200,
        json={
            "ResultCode": "1",
            "ResultDesc": "The transaction is still under processing",
        },
    )

    result = _mpesa_query_response(response)

    assert result[MPESA_QUERY_STATUS_KEY] == MPESA_QUERY_PENDING
    assert result["ResultCode"] == "1"


def test_mpesa_numeric_zero_query_result_is_success_without_message_matching():
    response = httpx.Response(
        200,
        json={
            "ResultCode": 0,
            "ResultDesc": "Diagnostic wording is not used for classification",
        },
    )

    result = _mpesa_query_response(response)

    assert result[MPESA_QUERY_STATUS_KEY] == MPESA_QUERY_SUCCEEDED
    assert result["ResultCode"] == 0


def test_kopokopo_signature_is_required(monkeypatch):
    import hashlib
    import hmac

    body = b'{"data":{"id":"event"}}'
    expected = hmac.new(b"callback-secret", body, hashlib.sha256).hexdigest()
    monkeypatch.setenv("KOPOKOPO_API_KEY", "callback-secret")
    from settings import get_settings

    get_settings.cache_clear()
    assert verify_kopokopo_signature(body, expected)
    assert not verify_kopokopo_signature(body, "bad")
    assert not verify_kopokopo_signature(body, None)


def test_successful_callback_is_idempotent(db, monkeypatch):
    router, package = _portal(db)
    session = PaymentSession(
        access_token_hash="x" * 64,
        idempotency_key="callback-idem",
        request_fingerprint="f" * 64,
        provider="mpesa",
        provider_request_id="checkout-idempotent",
        status="pending",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=payment_service.datetime.utcnow() + payment_service.timedelta(minutes=10),
    )
    db.add(session)
    db.commit()
    monkeypatch.setattr(payment_service, "provision_paid_session", lambda *_args: ("12", "generated-password"))

    complete_payment(session.public_id, "receipt-one", "0", "Paid")
    complete_payment(session.public_id, "receipt-one", "0", "Paid again")

    db.expire_all()
    assert db.query(Payment).count() == 1
    assert db.query(PaymentSession).filter_by(public_id=session.public_id).one().status == "provisioned"


@pytest.mark.asyncio
async def test_late_successful_callback_recovers_failed_payment(db, monkeypatch):
    router, package = _portal(db)
    session = PaymentSession(
        access_token_hash="x" * 64,
        idempotency_key="late-success-idem",
        request_fingerprint="f" * 64,
        provider="mpesa",
        provider_request_id="checkout-late-success",
        status="failed",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=payment_service.datetime.utcnow() - payment_service.timedelta(minutes=1),
    )
    db.add(session)
    db.commit()
    monkeypatch.setattr(payment_service, "provision_paid_session", lambda *_args: ("12", "generated-password"))

    await process_mpesa_callback(
        {
            "provider_request_id": session.provider_request_id,
            "result_code": "0",
            "result_description": "Paid",
            "amount": str(session.amount),
            "receipt": "late-receipt-one",
            "phone": session.phone_number,
        }
    )

    db.expire_all()
    recovered = db.query(PaymentSession).filter_by(public_id=session.public_id).one()
    assert recovered.status == "provisioned"
    assert recovered.provider_receipt == "late-receipt-one"
    assert db.query(Payment).filter_by(invoice=session.public_id).count() == 1


@pytest.mark.asyncio
async def test_nonzero_callback_result_code_marks_payment_failed(db):
    router, package = _portal(db)
    session = PaymentSession(
        access_token_hash="x" * 64,
        idempotency_key="callback-decline-idem",
        request_fingerprint="f" * 64,
        provider="mpesa",
        provider_request_id="checkout-declined",
        status="pending",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=payment_service.datetime.utcnow() + payment_service.timedelta(minutes=10),
    )
    db.add(session)
    db.commit()

    await process_mpesa_callback(
        {
            "provider_request_id": session.provider_request_id,
            "result_code": "1032",
            "result_description": "Diagnostic wording is not used for classification",
        }
    )

    db.expire_all()
    declined = db.query(PaymentSession).filter_by(public_id=session.public_id).one()
    assert declined.status == "failed"
    assert declined.result_code == "1032"
    assert db.query(Payment).count() == 0
