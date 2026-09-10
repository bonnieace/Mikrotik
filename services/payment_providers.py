"""HTTP clients for Daraja and Kopo Kopo incoming-payment APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from settings import Settings, get_settings


PROVIDER_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
MPESA_QUERY_PENDING_CODE = "500.001.1001"


@dataclass(frozen=True)
class ProviderInitiation:
    request_id: str
    customer_message: str


def normalize_kenyan_phone(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isdigit())
    if cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "254" + cleaned[1:]
    elif cleaned.startswith("7") and len(cleaned) == 9:
        cleaned = "254" + cleaned
    if not (cleaned.startswith("254") and len(cleaned) == 12 and cleaned[3] in {"1", "7"}):
        raise HTTPException(status_code=422, detail="Enter a valid Kenyan phone number")
    return cleaned


async def _mpesa_token(client: httpx.AsyncClient, settings: Settings) -> str:
    response = await client.get(
        f"{settings.mpesa_base_url}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(settings.mpesa_consumer_key, settings.mpesa_consumer_secret),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="M-Pesa authorization is unavailable")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="M-Pesa returned an invalid authorization response")
    return token


def _mpesa_token_sync(client: httpx.Client, settings: Settings) -> str:
    response = client.get(
        f"{settings.mpesa_base_url}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(settings.mpesa_consumer_key, settings.mpesa_consumer_secret),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="M-Pesa authorization is unavailable")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="M-Pesa returned an invalid authorization response")
    return token


def _mpesa_password(settings: Settings, timestamp: str) -> str:
    value = settings.mpesa_business_short_code + settings.mpesa_passkey + timestamp
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _mpesa_query_payload(settings: Settings, checkout_request_id: str, timestamp: str) -> dict:
    return {
        "BusinessShortCode": settings.mpesa_business_short_code,
        "Password": _mpesa_password(settings, timestamp),
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }


def _mpesa_query_response(response: httpx.Response) -> dict:
    """Normalize Daraja STK query responses while preserving an in-flight payment as pending."""
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="M-Pesa returned an invalid verification response") from exc

    code = str(data.get("errorCode") or data.get("ResultCode") or "")
    description = str(data.get("errorMessage") or data.get("ResultDesc") or "")
    normalized_description = description.lower()
    is_pending = (
        code == MPESA_QUERY_PENDING_CODE
        or "transaction is being processed" in normalized_description
        or "transaction is still being processed" in normalized_description
        or "transaction is under processing" in normalized_description
    )
    if is_pending:
        # Do not expose a ResultCode here: payment_service interprets the absence of a
        # terminal result as "keep polling" and will ask Daraja again on the next window.
        return {
            "pending": True,
            "errorCode": code or MPESA_QUERY_PENDING_CODE,
            "errorMessage": description or "The transaction is being processed",
        }

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="M-Pesa verification is unavailable")
    return data


async def initiate_mpesa(phone: str, amount: Decimal, public_id: str) -> ProviderInitiation:
    settings = get_settings()
    if amount != amount.to_integral_value():
        raise HTTPException(status_code=422, detail="M-Pesa packages must use whole KES amounts")
    callback_url = f"{settings.api_public_url}/api/v1/webhooks/mpesa/stk"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
        token = await _mpesa_token(client, settings)
        response = await client.post(
            f"{settings.mpesa_base_url}/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "BusinessShortCode": settings.mpesa_business_short_code,
                "Password": _mpesa_password(settings, timestamp),
                "Timestamp": timestamp,
                "TransactionType": settings.mpesa_transaction_type,
                "Amount": int(amount),
                "PartyA": phone,
                "PartyB": settings.mpesa_business_short_code,
                "PhoneNumber": phone,
                "CallBackURL": callback_url,
                "AccountReference": public_id[:12],
                "TransactionDesc": "Internet access",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="M-Pesa could not start the payment request")
    data = response.json()
    request_id = data.get("CheckoutRequestID")
    if not request_id or str(data.get("ResponseCode")) != "0":
        raise HTTPException(status_code=502, detail=data.get("CustomerMessage") or "M-Pesa rejected the request")
    return ProviderInitiation(request_id=request_id, customer_message=data.get("CustomerMessage") or "Check your phone to complete payment")


async def query_mpesa(checkout_request_id: str) -> dict:
    settings = get_settings()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
        token = await _mpesa_token(client, settings)
        response = await client.post(
            f"{settings.mpesa_base_url}/mpesa/stkpushquery/v1/query",
            headers={"Authorization": f"Bearer {token}"},
            json=_mpesa_query_payload(settings, checkout_request_id, timestamp),
        )
    return _mpesa_query_response(response)


def query_mpesa_sync(checkout_request_id: str) -> dict:
    """Synchronous STK status query for the existing sync public-status service path."""
    settings = get_settings()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    with httpx.Client(timeout=PROVIDER_TIMEOUT) as client:
        token = _mpesa_token_sync(client, settings)
        response = client.post(
            f"{settings.mpesa_base_url}/mpesa/stkpushquery/v1/query",
            headers={"Authorization": f"Bearer {token}"},
            json=_mpesa_query_payload(settings, checkout_request_id, timestamp),
        )
    return _mpesa_query_response(response)


async def _kopokopo_token(client: httpx.AsyncClient, settings: Settings) -> str:
    response = await client.post(
        f"{settings.kopokopo_base_url}/oauth/token",
        data={
            "client_id": settings.kopokopo_client_id,
            "client_secret": settings.kopokopo_client_secret,
            "grant_type": "client_credentials",
        },
        headers={"User-Agent": "uzanet/1.0"},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Kopo Kopo authorization is unavailable")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Kopo Kopo returned an invalid authorization response")
    return token


async def initiate_kopokopo(phone: str, amount: Decimal, public_id: str) -> ProviderInitiation:
    settings = get_settings()
    callback_url = f"{settings.api_public_url}/api/v1/webhooks/kopokopo/incoming-payment"
    async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
        token = await _kopokopo_token(client, settings)
        response = await client.post(
            f"{settings.kopokopo_base_url}/api/v2/incoming_payments",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "uzanet/1.0",
                "Accept": "application/json",
            },
            json={
                "payment_channel": "M-PESA STK Push",
                "till_number": settings.kopokopo_till_number,
                "subscriber": {"phone_number": f"+{phone}"},
                "amount": {"currency": "KES", "value": str(amount)},
                "metadata": {"reference": public_id, "notes": "Internet access"},
                "_links": {"callback_url": callback_url},
            },
        )
    if response.status_code != 201:
        raise HTTPException(status_code=502, detail="Kopo Kopo could not start the payment request")
    location = response.headers.get("Location")
    if not location:
        raise HTTPException(status_code=502, detail="Kopo Kopo returned no payment reference")
    request_id = urlparse(location).path.rstrip("/").split("/")[-1]
    return ProviderInitiation(request_id=request_id, customer_message="Check your phone to complete payment")


async def initiate_provider(provider: str, phone: str, amount: Decimal, public_id: str) -> ProviderInitiation:
    if provider == "mpesa":
        return await initiate_mpesa(phone, amount, public_id)
    if provider == "kopokopo":
        return await initiate_kopokopo(phone, amount, public_id)
    raise HTTPException(status_code=503, detail="Payment provider is not configured")


def verify_kopokopo_signature(raw_body: bytes, supplied_signature: str | None) -> bool:
    if not supplied_signature:
        return False
    expected = hmac.new(
        get_settings().kopokopo_api_key.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)


def mpesa_callback_values(payload: dict) -> dict:
    callback = payload.get("Body", {}).get("stkCallback", {})
    metadata = callback.get("CallbackMetadata", {}).get("Item", []) or []
    items = {item.get("Name"): item.get("Value") for item in metadata if item.get("Name")}
    return {
        "provider_request_id": callback.get("CheckoutRequestID"),
        "result_code": str(callback.get("ResultCode", "")),
        "result_description": callback.get("ResultDesc"),
        "amount": items.get("Amount"),
        "receipt": items.get("MpesaReceiptNumber"),
        "phone": str(items.get("PhoneNumber", "")),
    }


def kopokopo_callback_values(payload: dict) -> dict:
    attributes = payload.get("data", {}).get("attributes", {})
    event = attributes.get("event", {})
    resource = event.get("resource") or {}
    metadata = attributes.get("metadata") or {}
    return {
        "public_id": metadata.get("reference"),
        "provider_request_id": payload.get("data", {}).get("id"),
        "status": attributes.get("status"),
        "result_description": "; ".join(event.get("errors") or []),
        "amount": resource.get("amount"),
        "receipt": resource.get("reference"),
        "phone": str(resource.get("sender_phone_number", "")).lstrip("+"),
    }
