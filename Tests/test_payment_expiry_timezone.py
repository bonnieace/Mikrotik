from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from database.models import AdminUser, Package, PaymentSession, Router
from services.payment_service import _public_response


def test_public_payment_expiry_is_timezone_aware_utc(db):
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
    db.flush()
    session = PaymentSession(
        access_token_hash="x" * 64,
        idempotency_key="expiry-timezone",
        request_fingerprint="f" * 64,
        provider="mpesa",
        status="pending",
        phone_number="254712345678",
        phone_hash="p" * 64,
        amount=package.price,
        service_type="hotspot",
        router_id=router.id,
        package_id=package.id,
        expires_at=datetime(2026, 9, 9, 18, 20, 0),
    )
    db.add(session)
    db.commit()

    response = _public_response(session)

    assert response["expires_at"].tzinfo is not None
    assert response["expires_at"].utcoffset().total_seconds() == 0
    assert response["expires_at"].isoformat().endswith("+00:00")
