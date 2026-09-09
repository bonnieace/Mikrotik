"""Database models for the Uzanet MVP control plane."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, DECIMAL, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(125), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="isp")
    is_active = Column(Boolean, nullable=False, default=True)
    token_version = Column(Integer, nullable=False, default=0)
    failed_login_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    routers = relationship("Router", back_populates="owner")


class RegistrationAttempt(Base):
    __tablename__ = "registration_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_ip_hash = Column(String(64), nullable=True, index=True)
    email_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    name = Column(String(125), nullable=False)
    ip_address = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=8728)
    username = Column(String(125), nullable=False)
    # Fernet ciphertext. The legacy column name is retained for an in-place migration.
    password = Column(Text, nullable=False)
    owner_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True, index=True)
    portal_slug = Column(String(80), unique=True, nullable=False, index=True)
    portal_enabled = Column(Boolean, nullable=False, default=True)
    payment_provider = Column(String(32), nullable=False, default="mpesa")
    connection_mode = Column(String(32), nullable=False, default="l2tp")
    onboarding_status = Column(String(32), nullable=False, default="pending")
    onboarding_download_hash = Column(String(64), nullable=True)
    onboarding_script_encrypted = Column(Text, nullable=True)
    onboarding_token_hash = Column(String(64), nullable=True)
    onboarding_token_expires_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_error = Column(String(255), nullable=True)
    routeros_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("AdminUser", back_populates="routers")


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    name = Column(String(125), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    service_type = Column(String(50), nullable=False)
    validity_days = Column(Integer, nullable=False, default=1)
    validity_minutes = Column(Integer, nullable=False, default=1440)
    router_profile = Column(String(125), nullable=False, default="default")
    rate_limit = Column(String(64), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("router_id", "name", name="uq_package_router_name"),)


class HotspotUser(Base):
    __tablename__ = "hotspot_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    phone_number = Column(String(20), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    # Existing OTP column is retained as the RouterOS username for compatibility.
    otp = Column(String(125), nullable=False)
    password_encrypted = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime, nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("router_id", "otp", name="uq_hotspot_router_username"),)


class PPPUser(Base):
    __tablename__ = "ppp_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    name = Column(String(125), nullable=False)
    email = Column(String(125), nullable=True)
    pppoe_username = Column(String(125), nullable=False)
    # Fernet ciphertext. Never serialize this field.
    pppoe_password = Column(Text, nullable=False)
    mobile_number = Column(String(20), nullable=False)
    profile = Column(String(125), nullable=True)
    expires_on = Column(DateTime, nullable=True)
    location = Column(String(125), nullable=True)
    apartment = Column(String(125), nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False, index=True)
    role = Column(String(125), nullable=False, default="ppp_user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("router_id", "pppoe_username", name="uq_ppp_router_username"),)


class PaymentSession(Base):
    __tablename__ = "payment_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    access_token_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(80), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    provider = Column(String(32), nullable=False)
    provider_request_id = Column(String(255), nullable=True, unique=True)
    provider_receipt = Column(String(125), nullable=True, unique=True)
    status = Column(String(32), nullable=False, default="created", index=True)
    result_code = Column(String(32), nullable=True)
    result_description = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=False)
    phone_hash = Column(String(64), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="KES")
    service_type = Column(String(50), nullable=False)
    customer_reference = Column(String(125), nullable=True)
    client_ip_hash = Column(String(64), nullable=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    access_username = Column(String(125), nullable=True)
    access_password_encrypted = Column(Text, nullable=True)
    credentials_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("router_id", "idempotency_key", name="uq_payment_router_idempotency"),)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), unique=True, nullable=False, default=_uuid, index=True)
    invoice = Column(String(125), nullable=False, unique=True)
    provider = Column(String(32), nullable=False, default="mpesa")
    provider_receipt = Column(String(125), nullable=True, unique=True)
    status = Column(String(32), nullable=False, default="completed")
    amount = Column(DECIMAL(10, 2), nullable=False)
    user_type = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(16), nullable=False, default="info")
    event_type = Column(String(64), nullable=True)
    description = Column(Text, nullable=False)
    phone_number = Column(String(20), nullable=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=True, index=True)
