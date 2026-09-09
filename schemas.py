"""Typed request/response contracts for the versioned API."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateAdminUserRequest(StrictModel):
    username: str = Field(min_length=3, max_length=125)
    password: str = Field(min_length=12, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)
    role: Literal["superadmin", "isp"] = "isp"


class ISPRegistrationRequest(StrictModel):
    username: str = Field(min_length=3, max_length=60)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.lower()
        if not SLUG_RE.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and hyphens")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("enter a valid email address")
        return value


class ChangePasswordRequest(StrictModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class RouterCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=125)
    ip_address: str = Field(min_length=1, max_length=255)
    port: int = Field(default=8728, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=125)
    password: str = Field(min_length=8, max_length=256)
    portal_slug: str = Field(min_length=3, max_length=60)
    portal_enabled: bool = True
    payment_provider: Literal["mpesa", "kopokopo"] = "mpesa"

    @field_validator("portal_slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        value = value.lower()
        if not SLUG_RE.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and hyphens")
        return value


class RouterUpdateRequest(StrictModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=125)
    ip_address: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, min_length=1, max_length=125)
    password: Optional[str] = Field(default=None, min_length=8, max_length=256)
    portal_slug: Optional[str] = Field(default=None, min_length=3, max_length=60)
    portal_enabled: Optional[bool] = None
    payment_provider: Optional[Literal["mpesa", "kopokopo"]] = None

    @field_validator("portal_slug")
    @classmethod
    def valid_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.lower()
        if not SLUG_RE.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and hyphens")
        return value


class RouterOnboardingRequest(StrictModel):
    replace_managed_tunnel: bool = False
    name: str = Field(min_length=2, max_length=125)
    portal_slug: str = Field(min_length=3, max_length=60)
    payment_provider: Literal["mpesa", "kopokopo"] = "mpesa"

    @field_validator("portal_slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        value = value.lower()
        if not SLUG_RE.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and hyphens")
        return value


class RouterClaimRequest(StrictModel):
    token: str = Field(min_length=32, max_length=256)
    tunnel_ip: str = Field(min_length=1, max_length=255)
    routeros_version: Optional[str] = Field(default=None, max_length=64)


class PackageCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=125)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    service_type: Literal["hotspot", "pppoe"]
    validity_minutes: int = Field(ge=1, le=525_600)
    router_profile: str = Field(default="default", min_length=1, max_length=125)
    rate_limit: Optional[str] = Field(default=None, max_length=64)
    is_active: bool = True


class PackageUpdateRequest(StrictModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=125)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    validity_minutes: Optional[int] = Field(default=None, ge=1, le=525_600)
    router_profile: Optional[str] = Field(default=None, min_length=1, max_length=125)
    rate_limit: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None


class HotspotUserCreateRequest(StrictModel):
    phone_number: str = Field(min_length=10, max_length=20)
    username: Optional[str] = Field(default=None, min_length=4, max_length=125)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    package_uid: str


class PPPUserCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=125)
    email: Optional[str] = Field(default=None, max_length=125)
    pppoe_username: str = Field(min_length=3, max_length=125)
    pppoe_password: str = Field(min_length=8, max_length=128)
    mobile_number: str = Field(min_length=10, max_length=20)
    location: Optional[str] = Field(default=None, max_length=125)
    apartment: Optional[str] = Field(default=None, max_length=125)
    package_uid: str


class PPPRenewRequest(StrictModel):
    package_uid: str


class PublicPaymentRequest(StrictModel):
    package_uid: str
    phone_number: str = Field(min_length=10, max_length=20)
    customer_reference: Optional[str] = Field(default=None, max_length=125)


class PaymentRetryRequest(StrictModel):
    reason: Optional[str] = Field(default=None, max_length=255)
