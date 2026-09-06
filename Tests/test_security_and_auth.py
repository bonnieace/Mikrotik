from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database.models import AdminUser
from mono import app, pwd_context
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


def test_login_me_logout_revokes_token(db):
    user = AdminUser(
        username="operator",
        hashed_password=pwd_context.hash("a-long-test-password"),
        role="isp",
    )
    db.add(user)
    db.commit()

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/token",
            data={"username": "operator", "password": "a-long-test-password"},
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
