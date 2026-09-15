"""Transactional email delivery for account verification."""

from __future__ import annotations

import html
import os
from urllib.parse import quote

import httpx


BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def _email_config() -> tuple[str, str, str, str]:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "").strip()
    sender_name = os.getenv("BREVO_SENDER_NAME", "Uzanet").strip() or "Uzanet"
    portal_url = os.getenv("OPERATOR_PORTAL_URL", "").strip().rstrip("/")
    if not api_key or not sender_email or not portal_url:
        raise RuntimeError(
            "Email verification is not configured. Set BREVO_API_KEY, BREVO_SENDER_EMAIL and OPERATOR_PORTAL_URL."
        )
    if not portal_url.startswith("https://") and os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}:
        raise RuntimeError("OPERATOR_PORTAL_URL must use HTTPS in production")
    return api_key, sender_email, sender_name, portal_url


async def send_verification_email(email: str, isp_name: str, token: str) -> None:
    api_key, sender_email, sender_name, portal_url = _email_config()
    verification_url = f"{portal_url}/verify-email?token={quote(token, safe='')}"
    safe_name = html.escape(isp_name)
    safe_url = html.escape(verification_url, quote=True)

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": email, "name": isp_name}],
        "subject": "Verify your Uzanet ISP account",
        "htmlContent": (
            "<html><body style='font-family:Arial,sans-serif;color:#0b1c30'>"
            f"<p>Hi {safe_name},</p>"
            "<p>Verify your email address to activate your Uzanet ISP account.</p>"
            f"<p><a href='{safe_url}' style='display:inline-block;padding:12px 18px;background:#0b5cff;color:#fff;text-decoration:none;border-radius:8px'>Verify email</a></p>"
            "<p>If you did not create this account, you can ignore this email.</p>"
            "</body></html>"
        ),
        "tags": ["isp-email-verification"],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            BREVO_ENDPOINT,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=payload,
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError("Brevo could not send the verification email") from exc
