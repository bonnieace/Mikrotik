from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from database.models import AdminUser
from main import app, pwd_context
from security import decrypt_secret, encrypt_secret, is_encrypted
from settings import get_settings


def test_credentials_are_encrypted_at_rest():
    ciphertext = encrypt_secret("router-password")
    assert ciphertext != "router-password"
    assert is_encrypted(ciphertext)
    assert decrypt_secret(ciphertext) == "router-password"


def test_production_rejects_unsafe_configuration(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("ALLOWED_HOSTS", "*")
    monkeypatch.setenv("API_PUBLIC_URL", "http://api.invalid")
    monkeypatch.delenv("ROUTER_CREDENTIAL_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        get_settings()


def _capture_verification(monkeypatch):
    sent: dict[str, str] = {}

    async def fake_send(email: str, isp_name: str, token: str):
        sent.update(email=email, isp_name=isp_name, token=token)

    monkeypatch.setattr("services.registration_service.send_verification_email", fake_send)
    return sent


def test_public_isp_registration_generates_identifier_and_requires_verification(db, monkeypatch):
    sent = _capture_verification(monkeypatch)
    with TestClient(app) as client:
        registration = client.post(
            "/api/v1/auth/register",
            json={
                "isp_name": "New ISP Network",
                "email": "OWNER@EXAMPLE.COM",
                "password": "a-long-test-password",
            },
        )
        assert registration.status_code == 201
        assert registration.json() == {"status": "verification_required", "email": "owner@example.com"}

        user = db.query(AdminUser).filter(AdminUser.email == "owner@example.com").one()
        assert user.username.startswith("newispnetwork-")
        assert " " not in user.username
        assert user.username == user.username.lower()
        assert user.isp_name == "New ISP Network"
        assert user.is_active is False
        assert user.email_verified_at is None
        assert sent["email"] == "owner@example.com"
        assert sent["isp_name"] == "New ISP Network"
        assert sent["token"]

        pending_login = client.post(
            "/api/v1/auth/token",
            data={"username": "owner@example.com", "password": "a-long-test-password"},
        )
        assert pending_login.status_code == 403
        assert "Verify your email" in pending_login.json()["detail"]

        verification = client.post("/api/v1/auth/verify-email", json={"token": sent["token"]})
        assert verification.status_code == 200
        token = verification.json()["access_token"]
        me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"].startswith("newispnetwork-")
        assert me.json()["email"] == "owner@example.com"
        assert me.json()["role"] == "isp"

    db.refresh(user)
    assert user.is_active is True
    assert user.email_verified_at is not None
    assert user.email_verification_token_hash is None
    assert pwd_context.verify("a-long-test-password", user.hashed_password)


def test_public_isp_registration_rejects_duplicate_email(db, monkeypatch):
    _capture_verification(monkeypatch)
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/auth/register",
            json={
                "isp_name": "First ISP",
                "email": "first@example.com",
                "password": "a-long-test-password",
            },
        )
        assert first.status_code == 201

        duplicate_email = client.post(
            "/api/v1/auth/register",
            json={
                "isp_name": "Another ISP",
                "email": "FIRST@example.com",
                "password": "another-long-password",
            },
        )
        assert duplicate_email.status_code == 409


def test_public_isp_registration_cannot_choose_privileged_role(db, monkeypatch):
    _capture_verification(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "isp_name": "Tenant ISP",
                "email": "tenant@example.com",
                "password": "a-long-test-password",
                "role": "superadmin",
            },
        )
        assert response.status_code == 422
        assert db.query(AdminUser).filter(AdminUser.email == "tenant@example.com").first() is None


def test_resend_verification_rotates_token(db, monkeypatch):
    sent = _capture_verification(monkeypatch)
    monkeypatch.setenv("EMAIL_VERIFICATION_RESEND_SECONDS", "30")
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={
                "isp_name": "Resend ISP",
                "email": "resend@example.com",
                "password": "a-long-test-password",
            },
        ).status_code == 201
        first_token = sent["token"]
        user = db.query(AdminUser).filter(AdminUser.email == "resend@example.com").one()
        user.email_verification_sent_at = datetime.utcnow() - timedelta(minutes=2)
        db.commit()

        resend = client.post("/api/v1/auth/resend-verification", json={"email": "resend@example.com"})
        assert resend.status_code == 202
        assert sent["token"] != first_token
        assert client.post("/api/v1/auth/verify-email", json={"token": first_token}).status_code == 400
        assert client.post("/api/v1/auth/verify-email", json={"token": sent["token"]}).status_code == 200


def test_login_me_logout_revokes_token(db):
    user = AdminUser(
        username="operator",
        email="operator@example.com",
        email_verified_at=datetime.utcnow(),
        hashed_password=pwd_context.hash("a-long-test-password"),
        role="isp",
    )
    db.add(user)
    db.commit()

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/token",
            data={"username": "operator@example.com", "password": "a-long-test-password"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["username"] == "operator"
        assert me.headers["x-content-type-options"] == "nosniff"

        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/me", headers=headers).status_code == 401


def test_correct_password_can_clear_temporary_lock(db):
    user = AdminUser(
        username="locked-operator",
        hashed_password=pwd_context.hash("correct-long-password"),
        role="isp",
        locked_until=datetime.utcnow() + timedelta(minutes=15),
        failed_login_count=0,
    )
    db.add(user)
    db.commit()

    with TestClient(app) as client:
        wrong = client.post(
            "/api/v1/auth/token",
            data={"username": "locked-operator", "password": "still-wrong-password"},
        )
        assert wrong.status_code == 429

        correct = client.post(
            "/api/v1/auth/token",
            data={"username": "locked-operator", "password": "correct-long-password"},
        )
        assert correct.status_code == 200

    db.refresh(user)
    assert user.locked_until is None
    assert user.failed_login_count == 0
