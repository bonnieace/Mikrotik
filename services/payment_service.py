"""Idempotent asynchronous payment sessions and access provisioning."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database import crud
from database.models import Package, Payment, PaymentSession, Router
from database.session import SessionLocal
from schemas import PublicPaymentRequest
from security import (
    constant_time_token_matches,
    decrypt_secret,
    hash_token,
    mask_phone,
    payment_access_token,
    private_hash,
)
from services.access_service import prepare_paid_hotspot_session, provision_paid_session
from services.payment_providers import (
    initiate_provider,
    normalize_kenyan_phone,
    query_mpesa,
    query_mpesa_sync,
)
from settings import get_settings


# A provider can deliver a verified successful callback after local expiry or an
# earlier non-success callback. ``failed`` is therefore recoverable, not final.
CALLBACK_IGNORED_STATUSES = {"provisioned", "manual_review"}
MPESA_STATUS_QUERY_SECONDS = 5


def _decimal_or_none(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _query_result_code(result: dict) -> str:
    result_code = result.get("ResultCode")
    if result_code is not None:
        return str(result_code)
    error_code = result.get("errorCode")
    return "" if error_code is None else str(error_code)


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fingerprint(package_uid: str, phone: str, customer_reference: str | None) -> str:
    value = json.dumps(
        {"package_uid": package_uid, "phone": phone, "customer_reference": customer_reference or ""},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_response(row: PaymentSession, *, include_token: bool = False) -> dict:
    response = {
        "payment_id": row.public_id,
        "status": row.status,
        "provider": row.provider,
        "amount": row.amount,
        "currency": row.currency,
        "service_type": row.service_type,
        "phone_number": mask_phone(row.phone_number),
        "message": row.result_description,
        "expires_at": _utc_datetime(row.expires_at),
    }
    if include_token:
        response["status_token"] = payment_access_token(row.public_id)
    if (
        row.status == "provisioned"
        and row.service_type == "hotspot"
        and row.credentials_expires_at
        and row.credentials_expires_at >= datetime.utcnow()
        and row.access_password_encrypted
    ):
        response["credentials"] = {
            "username": row.access_username,
            "password": decrypt_secret(row.access_password_encrypted),
        }
    elif row.status == "provisioned" and row.service_type == "pppoe":
        response["account"] = row.access_username
    return response


def public_portal(portal_slug: str) -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        router = crud.get_router_by_portal_slug(db, portal_slug)
        if router is None or not router.portal_enabled:
            raise HTTPException(status_code=404, detail="Portal not found")
        if router.payment_provider not in settings.payment_providers:
            raise HTTPException(status_code=503, detail="This portal's payment provider is not enabled")
        packages = crud.get_packages(db, router.id, active_only=True)
        return {
            "isp_identifier": router.owner.username if router.owner else None,
            "portal_slug": router.portal_slug,
            "name": router.name,
            "payment_provider": router.payment_provider,
            "packages": [
                {
                    "uid": package.uid,
                    "name": package.name,
                    "description": package.description,
                    "price": package.price,
                    "currency": "KES",
                    "service_type": package.service_type,
                    "validity_minutes": package.validity_minutes,
                    "rate_limit": package.rate_limit,
                }
                for package in packages
            ],
        }
    finally:
        db.close()


def _prepare_payment_access(public_id: str) -> bool:
    """Prepare a HotSpot RouterOS user before payment confirmation.

    Credentials remain encrypted in the payment session and are never serialized while
    the session is pending. PPPoE renewals keep their existing post-payment path.
    """
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row is None or row.service_type != "hotspot":
            return False
        package = db.query(Package).filter(Package.id == row.package_id).first()
        if package is None:
            raise HTTPException(status_code=404, detail="Package not found")
        prepare_paid_hotspot_session(db, row, package)
        crud.create_log(db, "Hotspot access prepared", router_id=row.router_id, event_type="payment.access_prepared")
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _log_prepare_failure(public_id: str) -> None:
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row is not None:
            crud.create_log(
                db,
                "Hotspot access preparation failed; will retry after payment confirmation",
                router_id=row.router_id,
                level="error",
                event_type="payment.access_prepare_failed",
            )
            db.commit()
    finally:
        db.close()


async def create_public_payment(
    portal_slug: str,
    body: PublicPaymentRequest,
    idempotency_key: str,
    client_ip: str | None,
) -> dict:
    settings = get_settings()
    phone = normalize_kenyan_phone(body.phone_number)
    client_ip_hash = private_hash(client_ip) if client_ip else None
    phone_hash = private_hash(phone)
    fingerprint = _fingerprint(body.package_uid, phone, body.customer_reference)
    db = SessionLocal()
    try:
        router = crud.get_router_by_portal_slug(db, portal_slug)
        if router is None or not router.portal_enabled:
            raise HTTPException(status_code=404, detail="Portal not found")
        if router.payment_provider not in settings.payment_providers:
            raise HTTPException(status_code=503, detail="This portal's payment provider is not enabled")
        package = crud.get_package_by_uid(db, body.package_uid)
        if package is None or package.router_id != router.id or not package.is_active:
            raise HTTPException(status_code=404, detail="Package not found")
        if package.service_type == "pppoe" and not body.customer_reference:
            raise HTTPException(status_code=422, detail="PPPoE account reference is required")

        existing = crud.get_payment_session_by_idempotency(db, router.id, idempotency_key)
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for another request")
            return _public_response(existing, include_token=True)

        since = datetime.utcnow() - timedelta(minutes=settings.public_payment_window_minutes)
        limiter = db.query(PaymentSession).filter(PaymentSession.created_at >= since)
        limiter = limiter.filter(
            or_(
                PaymentSession.phone_hash == phone_hash,
                PaymentSession.client_ip_hash == client_ip_hash if client_ip_hash else False,
            )
        )
        if limiter.count() >= settings.public_payment_limit:
            raise HTTPException(status_code=429, detail="Too many payment attempts. Try again shortly")

        row = PaymentSession(
            access_token_hash="pending",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            provider=router.payment_provider or settings.payment_provider,
            status="created",
            phone_number=phone,
            phone_hash=phone_hash,
            amount=package.price,
            service_type=package.service_type,
            customer_reference=body.customer_reference,
            client_ip_hash=client_ip_hash,
            router_id=router.id,
            package_id=package.id,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.payment_session_minutes),
        )
        db.add(row)
        db.flush()
        row.access_token_hash = hash_token(payment_access_token(row.public_id))
        db.commit()
        db.refresh(row)
        public_id = row.public_id
        provider = row.provider
        amount = Decimal(row.amount)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate payment request") from exc
    finally:
        db.close()

    provider_task = asyncio.create_task(initiate_provider(provider, phone, amount, public_id))
    prepare_task = asyncio.create_task(asyncio.to_thread(_prepare_payment_access, public_id))
    initiation_result, preparation_result = await asyncio.gather(
        provider_task,
        prepare_task,
        return_exceptions=True,
    )

    if isinstance(preparation_result, Exception):
        await asyncio.to_thread(_log_prepare_failure, public_id)

    if isinstance(initiation_result, Exception):
        failed_db = SessionLocal()
        try:
            failed = crud.get_payment_session_by_public_id(failed_db, public_id)
            if failed and failed.status == "created":
                failed.status = "failed"
                failed.result_description = "Payment provider is unavailable"
                failed_db.commit()
        finally:
            failed_db.close()
        if isinstance(initiation_result, HTTPException):
            raise initiation_result
        raise HTTPException(status_code=502, detail="Payment provider is unavailable") from initiation_result

    initiation = initiation_result
    update_db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(update_db, public_id)
        row.provider_request_id = initiation.request_id
        row.status = "pending"
        row.result_description = initiation.customer_message
        crud.create_log(update_db, "Payment initiated", router_id=row.router_id, event_type="payment.initiated")
        update_db.commit()
        update_db.refresh(row)
        return _public_response(row, include_token=True)
    finally:
        update_db.close()


def _record_provider_query_state(public_id: str, code: str, description: str | None) -> None:
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row and row.status == "pending":
            row.result_code = code[:32]
            row.result_description = str(description or "Payment confirmation is pending")[:255]
            db.commit()
    finally:
        db.close()


def _query_pending_mpesa(public_id: str, request_id: str) -> None:
    try:
        result = query_mpesa_sync(request_id)
    except Exception:
        return

    code = _query_result_code(result)
    if code == "0":
        try:
            complete_payment(
                public_id,
                result.get("MpesaReceiptNumber"),
                code,
                result.get("ResultDesc"),
            )
        except Exception:
            # complete_payment records provisioning_failed before re-raising.
            return
    else:
        _record_provider_query_state(
            public_id,
            code,
            result.get("ResultDesc") or result.get("errorMessage"),
        )


def get_public_payment(public_id: str, status_token: str) -> dict:
    request_id = None
    should_query_mpesa = False
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row is None or not constant_time_token_matches(status_token, row.access_token_hash):
            raise HTTPException(status_code=404, detail="Payment not found")
        token_expires_at = row.created_at + timedelta(minutes=get_settings().payment_status_token_minutes)
        if token_expires_at < datetime.utcnow():
            raise HTTPException(status_code=404, detail="Payment not found")
        if row.status in {"created", "pending"} and row.expires_at < datetime.utcnow():
            row.status = "failed"
            row.result_description = "Payment session expired"
            db.commit()
        elif row.status == "pending" and row.provider == "mpesa" and row.provider_request_id:
            cutoff = datetime.utcnow() - timedelta(seconds=MPESA_STATUS_QUERY_SECONDS)
            if row.updated_at <= cutoff:
                # Claim this provider-query window so rapid browser polling does not
                # query Daraja on every request. If the browser disappears, jobs.py
                # can still reconcile the session after its normal stale cutoff.
                row.updated_at = datetime.utcnow()
                request_id = row.provider_request_id
                db.commit()
                should_query_mpesa = True
        response = _public_response(row)
    finally:
        db.close()

    if should_query_mpesa and request_id:
        _query_pending_mpesa(public_id, request_id)
        verify_db = SessionLocal()
        try:
            row = crud.get_payment_session_by_public_id(verify_db, public_id)
            if row is None or not constant_time_token_matches(status_token, row.access_token_hash):
                raise HTTPException(status_code=404, detail="Payment not found")
            return _public_response(row)
        finally:
            verify_db.close()
    return response


async def process_mpesa_callback(values: dict) -> None:
    request_id = values.get("provider_request_id")
    if not request_id:
        return
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_provider_id(db, request_id)
        if row is None or row.provider != "mpesa" or row.status in CALLBACK_IGNORED_STATUSES:
            return
        if values.get("result_code") != "0":
            row.status = "failed"
            row.result_code = values.get("result_code")
            row.result_description = str(values.get("result_description") or "Payment failed")[:255]
            db.commit()
            return
        public_id = row.public_id
        expected_amount = Decimal(row.amount)
        expected_phone = row.phone_number
    finally:
        db.close()

    if _decimal_or_none(values.get("amount")) != expected_amount or values.get("phone") != expected_phone:
        _mark_manual_review(public_id, "M-Pesa callback did not match the payment request")
        return
    if get_settings().mpesa_verify_callback:
        verification = await query_mpesa(request_id)
        if str(verification.get("ResultCode")) != "0":
            _mark_manual_review(public_id, "M-Pesa callback verification failed")
            return
    await asyncio.to_thread(complete_payment, public_id, values.get("receipt"), "0", values.get("result_description"))


def process_kopokopo_callback(values: dict) -> None:
    public_id = values.get("public_id")
    if not public_id:
        return
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row is None or row.provider != "kopokopo" or row.status in CALLBACK_IGNORED_STATUSES:
            return
        if str(values.get("status", "")).lower() != "success":
            row.status = "failed"
            row.result_description = str(values.get("result_description") or "Payment failed")[:255]
            db.commit()
            return
        if _decimal_or_none(values.get("amount")) != Decimal(row.amount) or values.get("phone") != row.phone_number:
            row.status = "manual_review"
            row.result_description = "Kopo Kopo callback did not match the payment request"
            db.commit()
            return
    finally:
        db.close()
    complete_payment(public_id, values.get("receipt"), "0", values.get("result_description"))


def complete_payment(public_id: str, receipt: str | None, result_code: str, description: str | None) -> None:
    if str(result_code) != "0":
        raise ValueError("complete_payment requires a successful provider result code")
    db = SessionLocal()
    try:
        row = (
            db.query(PaymentSession)
            .filter(PaymentSession.public_id == public_id)
            .with_for_update()
            .first()
        )
        if row is None or row.status == "provisioned":
            return
        row.status = "provisioning"
        row.provider_receipt = receipt
        row.result_code = result_code
        row.result_description = str(description or "Payment received")[:255]
        package = db.query(Package).filter(Package.id == row.package_id).first()
        if package is None:
            row.status = "manual_review"
            row.result_description = "Paid package no longer exists"
            db.commit()
            return
        try:
            user_id, _ = provision_paid_session(db, row, package)
            payment = db.query(Payment).filter(Payment.invoice == row.public_id).first()
            if payment is None:
                db.add(
                    Payment(
                        invoice=row.public_id,
                        provider=row.provider,
                        provider_receipt=receipt,
                        status="completed",
                        amount=row.amount,
                        user_type=row.service_type,
                        user_id=int(user_id),
                        package_id=row.package_id,
                        router_id=row.router_id,
                    )
                )
            row.status = "provisioned"
            row.result_description = "Payment confirmed and access activated"
            crud.create_log(db, "Payment provisioned", router_id=row.router_id, event_type="payment.provisioned")
            db.commit()
        except Exception:
            db.rollback()
            failed = crud.get_payment_session_by_public_id(db, public_id)
            if failed:
                failed.status = "provisioning_failed"
                failed.result_description = "Payment received; access activation needs retry"
                crud.create_log(db, "Payment provisioning failed", router_id=failed.router_id, level="error", event_type="payment.provisioning_failed")
                db.commit()
            raise
    finally:
        db.close()


def retry_provisioning(public_id: str) -> dict:
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Payment session not found")
        if row.status not in {"provisioning", "provisioning_failed", "paid"}:
            raise HTTPException(status_code=409, detail="Payment is not waiting for provisioning")
        receipt = row.provider_receipt
    finally:
        db.close()
    complete_payment(public_id, receipt, "0", "Provisioning retried by administrator")
    verify_db = SessionLocal()
    try:
        return _public_response(crud.get_payment_session_by_public_id(verify_db, public_id))
    finally:
        verify_db.close()


def _mark_manual_review(public_id: str, reason: str) -> None:
    db = SessionLocal()
    try:
        row = crud.get_payment_session_by_public_id(db, public_id)
        if row and row.status != "provisioned":
            row.status = "manual_review"
            row.result_description = reason[:255]
            db.commit()
    finally:
        db.close()


async def reconcile_pending_payments(limit: int = 25) -> dict:
    """Reconcile stale M-Pesa sessions when a provider callback was missed.

    Kopo Kopo is webhook-only in this MVP because its incoming-payment API returns a
    resource URL rather than the Daraja-style authoritative STK query response.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=30)
    db = SessionLocal()
    try:
        rows = (
            db.query(PaymentSession)
            .filter(
                PaymentSession.provider == "mpesa",
                PaymentSession.status == "pending",
                PaymentSession.updated_at <= cutoff,
                PaymentSession.expires_at > datetime.utcnow(),
            )
            .order_by(PaymentSession.updated_at.asc())
            .limit(limit)
            .all()
        )
        candidates = [(row.public_id, row.provider_request_id) for row in rows if row.provider_request_id]
    finally:
        db.close()

    provisioned = 0
    failed = 0
    still_pending = 0
    for public_id, request_id in candidates:
        try:
            result = await query_mpesa(request_id)
        except Exception:
            still_pending += 1
            continue
        code = _query_result_code(result)
        if code == "0":
            await asyncio.to_thread(
                complete_payment,
                public_id,
                result.get("MpesaReceiptNumber"),
                code,
                result.get("ResultDesc"),
            )
            provisioned += 1
        else:
            await asyncio.to_thread(
                _record_provider_query_state,
                public_id,
                code,
                result.get("ResultDesc") or result.get("errorMessage"),
            )
            still_pending += 1
    return {"checked": len(candidates), "provisioned": provisioned, "failed": failed, "pending": still_pending}


def expire_payment_sessions() -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(PaymentSession)
            .filter(PaymentSession.status.in_(("created", "pending")), PaymentSession.expires_at <= datetime.utcnow())
            .all()
        )
        for row in rows:
            row.status = "failed"
            row.result_description = "Payment session expired"
        db.commit()
        return len(rows)
    finally:
        db.close()


def serialize_payment(row: Payment) -> dict:
    return {
        "uid": row.uid,
        "invoice": row.invoice,
        "provider": row.provider,
        "provider_receipt": row.provider_receipt,
        "status": row.status,
        "amount": row.amount,
        "user_type": row.user_type,
        "user_id": row.user_id,
        "package_id": row.package_id,
        "created_at": row.created_at,
    }


def list_payments(router: Router) -> list[dict]:
    db = SessionLocal()
    try:
        return [serialize_payment(row) for row in crud.get_payments(db, router.id)]
    finally:
        db.close()


def list_payment_sessions(router: Router) -> list[dict]:
    db = SessionLocal()
    try:
        return [
            {
                "payment_id": row.public_id,
                "provider": row.provider,
                "provider_receipt": row.provider_receipt,
                "status": row.status,
                "amount": row.amount,
                "currency": row.currency,
                "service_type": row.service_type,
                "customer_reference": row.customer_reference,
                "phone_number": mask_phone(row.phone_number),
                "message": row.result_description,
                "can_retry": row.status in {"paid", "provisioning", "provisioning_failed"},
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "expires_at": row.expires_at,
            }
            for row in crud.get_payment_sessions(db, router.id)
        ]
    finally:
        db.close()


# Compatibility reporting helpers.
def get_payments(router_id=None):
    db = SessionLocal()
    try:
        return [serialize_payment(row) | {"id": row.id} for row in crud.get_payments(db, router_id)]
    finally:
        db.close()


def get_payments_by_user_type(user_type, router_id=None):
    db = SessionLocal()
    try:
        return [serialize_payment(row) | {"id": row.id} for row in crud.get_payments_by_user_type(db, user_type, router_id)]
    finally:
        db.close()


def get_total_payment_by_user_type(user_type, router_id=None):
    return sum((row["amount"] for row in get_payments_by_user_type(user_type, router_id)), 0)


def get_total_payment_for_today_by_user_type(user_type, router_id=None):
    db = SessionLocal()
    try:
        return crud.get_payment_totals_for_today_by_user_type(db, user_type, router_id)
    finally:
        db.close()
