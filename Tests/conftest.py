from __future__ import annotations

import os

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/uzanet-mvp-tests.sqlite3")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ.setdefault("ROUTER_CREDENTIAL_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("ROUTER_CONTROL_HOST", "vpn.test.invalid")
os.environ.setdefault("ROUTER_CONTROL_CIDR", "10.77.0.0/24")
os.environ.setdefault("ROUTER_ALLOWED_CIDRS", "10.77.0.0/24,127.0.0.0/8")
os.environ.setdefault("PAYMENT_PROVIDER", "mpesa")
os.environ.setdefault("PAYMENT_PROVIDERS", "mpesa,kopokopo")
os.environ.setdefault("MPESA_VERIFY_CALLBACK", "false")

from database.session import Base, SessionLocal, engine  # noqa: E402
import database.models  # noqa: E402,F401
from settings import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove() if hasattr(SessionLocal, "remove") else None
    get_settings.cache_clear()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
