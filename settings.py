"""Runtime configuration with production-safe validation.

The application deliberately does not load credentials from source-code defaults.  Local
development may omit provider settings, but production refuses to start with an unsafe JWT
secret, wildcard CORS, missing credential encryption, or an incomplete payment provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from cryptography.fernet import Fernet


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in os.getenv(name, default).split(",") if item.strip())


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    environment: str
    secret_key: str
    access_token_expire_minutes: int
    cors_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    docs_enabled: bool
    api_public_url: str
    router_credential_key: str
    router_connect_timeout_seconds: float
    router_operation_timeout_seconds: float
    router_control_host: str
    router_control_cidr: str
    router_allowed_cidrs: tuple[str, ...]
    onboarding_token_minutes: int
    payment_session_minutes: int
    payment_status_token_minutes: int
    public_payment_limit: int
    public_payment_window_minutes: int
    payment_provider: str
    payment_providers: tuple[str, ...]

    mpesa_base_url: str
    mpesa_consumer_key: str
    mpesa_consumer_secret: str
    mpesa_business_short_code: str
    mpesa_passkey: str
    mpesa_transaction_type: str
    mpesa_verify_callback: bool

    kopokopo_base_url: str
    kopokopo_client_id: str
    kopokopo_client_secret: str
    kopokopo_api_key: str
    kopokopo_till_number: str

    @property
    def is_production(self) -> bool:
        return self.environment in {"production", "prod"}

    def validate(self) -> None:
        errors: list[str] = []
        if self.is_production:
            if len(self.secret_key) < 32 or self.secret_key == "change-me-in-production":
                errors.append("SECRET_KEY must be a random value of at least 32 characters")
            if not self.router_credential_key:
                errors.append("ROUTER_CREDENTIAL_KEY is required")
            else:
                try:
                    Fernet(self.router_credential_key.encode("ascii"))
                except (ValueError, TypeError):
                    errors.append("ROUTER_CREDENTIAL_KEY must be a valid Fernet key")
            if not self.cors_origins or "*" in self.cors_origins:
                errors.append("CORS_ORIGINS must contain explicit HTTPS origins")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                errors.append("ALLOWED_HOSTS must contain explicit hostnames")
            if any(urlparse(origin).scheme != "https" for origin in self.cors_origins):
                errors.append("CORS_ORIGINS must use HTTPS in production")
            if urlparse(self.api_public_url).scheme != "https":
                errors.append("API_PUBLIC_URL must use HTTPS in production")
            if not self.router_control_host or not self.router_control_cidr:
                errors.append("ROUTER_CONTROL_HOST and ROUTER_CONTROL_CIDR are required")

            unknown = set(self.payment_providers) - {"mpesa", "kopokopo"}
            if not self.payment_providers or unknown:
                errors.append("PAYMENT_PROVIDERS must contain only 'mpesa' and/or 'kopokopo'")
            if self.payment_provider not in self.payment_providers:
                errors.append("PAYMENT_PROVIDER must be included in PAYMENT_PROVIDERS")
            required: dict[str, str] = {}
            if "mpesa" in self.payment_providers:
                required.update({
                    "MPESA_CONSUMER_KEY": self.mpesa_consumer_key,
                    "MPESA_CONSUMER_SECRET": self.mpesa_consumer_secret,
                    "MPESA_BUSINESS_SHORT_CODE": self.mpesa_business_short_code,
                    "MPESA_PASSKEY": self.mpesa_passkey,
                })
                if not self.mpesa_verify_callback:
                    errors.append("MPESA_VERIFY_CALLBACK must be true in production")
                if urlparse(self.mpesa_base_url).scheme != "https":
                    errors.append("MPESA_BASE_URL must use HTTPS in production")
            if "kopokopo" in self.payment_providers:
                required.update({
                    "KOPOKOPO_CLIENT_ID": self.kopokopo_client_id,
                    "KOPOKOPO_CLIENT_SECRET": self.kopokopo_client_secret,
                    "KOPOKOPO_API_KEY": self.kopokopo_api_key,
                    "KOPOKOPO_TILL_NUMBER": self.kopokopo_till_number,
                })
                if urlparse(self.kopokopo_base_url).scheme != "https":
                    errors.append("KOPOKOPO_BASE_URL must use HTTPS in production")
            errors.extend(f"{name} is required" for name, value in required.items() if not value)

        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings(
        environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
        secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        cors_origins=_csv("CORS_ORIGINS", "http://localhost:5173"),
        allowed_hosts=_csv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"),
        docs_enabled=_bool("ENABLE_API_DOCS", True),
        api_public_url=os.getenv("API_PUBLIC_URL", "http://localhost:8000").rstrip("/"),
        router_credential_key=os.getenv("ROUTER_CREDENTIAL_KEY", ""),
        router_connect_timeout_seconds=float(os.getenv("ROUTER_CONNECT_TIMEOUT_SECONDS", "4")),
        router_operation_timeout_seconds=float(os.getenv("ROUTER_OPERATION_TIMEOUT_SECONDS", "10")),
        router_control_host=os.getenv("ROUTER_CONTROL_HOST", ""),
        router_control_cidr=os.getenv("ROUTER_CONTROL_CIDR", "10.10.10.0/24"),
        router_allowed_cidrs=_csv("ROUTER_ALLOWED_CIDRS", os.getenv("ROUTER_CONTROL_CIDR", "10.10.10.0/24")),
        onboarding_token_minutes=int(os.getenv("ONBOARDING_TOKEN_MINUTES", "30")),
        payment_session_minutes=int(os.getenv("PAYMENT_SESSION_MINUTES", "15")),
        payment_status_token_minutes=int(os.getenv("PAYMENT_STATUS_TOKEN_MINUTES", "30")),
        public_payment_limit=int(os.getenv("PUBLIC_PAYMENT_LIMIT", "3")),
        public_payment_window_minutes=int(os.getenv("PUBLIC_PAYMENT_WINDOW_MINUTES", "5")),
        payment_provider=os.getenv("PAYMENT_PROVIDER", "mpesa").strip().lower(),
        payment_providers=_csv("PAYMENT_PROVIDERS", os.getenv("PAYMENT_PROVIDER", "mpesa").strip().lower()),
        mpesa_base_url=os.getenv("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke").rstrip("/"),
        mpesa_consumer_key=os.getenv("MPESA_CONSUMER_KEY", ""),
        mpesa_consumer_secret=os.getenv("MPESA_CONSUMER_SECRET", ""),
        mpesa_business_short_code=os.getenv("MPESA_BUSINESS_SHORT_CODE", ""),
        mpesa_passkey=os.getenv("MPESA_PASSKEY", ""),
        mpesa_transaction_type=os.getenv("MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"),
        mpesa_verify_callback=_bool("MPESA_VERIFY_CALLBACK", True),
        kopokopo_base_url=os.getenv("KOPOKOPO_BASE_URL", "https://sandbox.kopokopo.com").rstrip("/"),
        kopokopo_client_id=os.getenv("KOPOKOPO_CLIENT_ID", ""),
        kopokopo_client_secret=os.getenv("KOPOKOPO_CLIENT_SECRET", ""),
        kopokopo_api_key=os.getenv("KOPOKOPO_API_KEY", ""),
        kopokopo_till_number=os.getenv("KOPOKOPO_TILL_NUMBER", ""),
    )
    settings.validate()
    return settings
