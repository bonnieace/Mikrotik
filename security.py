"""Hashing, token, and application-level secret encryption helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken

from settings import get_settings


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def private_hash(value: str) -> str:
    return hmac.new(
        get_settings().secret_key.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def constant_time_token_matches(value: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(value), expected_hash)


def random_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def payment_access_token(public_id: str) -> str:
    """Derive a non-enumerable status token so idempotent retries return the same token."""
    return hmac.new(
        get_settings().secret_key.encode("utf-8"),
        f"payment:{public_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _fernet() -> Fernet:
    configured = get_settings().router_credential_key
    if configured:
        key = configured.encode("ascii")
    else:
        # Development-only deterministic key. Production validation rejects an omitted key.
        digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
        key = urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Stored credential is not encrypted with the active key") from exc


def is_encrypted(value: str) -> bool:
    if not value:
        return False
    try:
        _fernet().decrypt(value.encode("ascii"))
        return True
    except (InvalidToken, ValueError):
        return False


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-3:]}" if len(phone) >= 8 else "***"
