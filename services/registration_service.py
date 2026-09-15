"""Self-service ISP registration, email verification, and email-aware login."""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database.models import AdminUser
from database.session import SessionLocal
from schemas import EmailVerificationRequest, ISPRegistrationRequest, ResendVerificationRequest
from security import hash_token, random_token
from services.email_service import send_verification_email
from settings import get_settings


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DUMMY_HASH = "$2b$12$2b2xVQyQmD/3C7Y62A/BKuF7VL2NfFv.i3I9qLfVFe1qgD0uYPZZK"


def _verification_minutes() -> int:
    return max(10, int(os.getenv("EMAIL_VERIFICATION_MINUTES", "60")))


def _resend_seconds() -> int:
    return max(30, int(os.getenv("EMAIL_VERIFICATION_RESEND_SECONDS", "60")))


def _isp_identifier(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    compact = re.sub(r"\s+", "", ascii_name)
    compact = re.sub(r"[^a-z0-9]", "", compact)
    if not compact:
        raise HTTPException(status_code=422, detail="Enter an ISP name containing letters or numbers")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{compact[:38]}-{stamp}"


def _issue_access_token(user: AdminUser) -> dict:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    encoded = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "ver": user.token_version,
            "iss": "uzanet-api",
            "aud": "uzanet-admin",
            "iat": now_utc,
            "exp": now_utc + timedelta(minutes=settings.access_token_expire_minutes),
            "jti": str(uuid.uuid4()),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    return {
        "access_token": encoded,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


def _find_login_user(db, identifier: str) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.username == identifier).first()
    if user is not None:
        return user
    lowered = identifier.strip().lower()
    return db.query(AdminUser).filter(func.lower(AdminUser.email) == lowered).first()


@router.post("/register", status_code=201)
async def register_isp(body: ISPRegistrationRequest):
    db = SessionLocal()
    try:
        email = body.email.lower()
        if db.query(AdminUser).filter(func.lower(AdminUser.email) == email).first():
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        token = random_token()
        now = datetime.utcnow()
        user = AdminUser(
            username=_isp_identifier(body.isp_name),
            isp_name=body.isp_name,
            email=email,
            email_verified_at=None,
            email_verification_token_hash=hash_token(token),
            email_verification_expires_at=now + timedelta(minutes=_verification_minutes()),
            email_verification_sent_at=now,
            hashed_password=pwd_context.hash(body.password),
            role="isp",
            is_active=False,
        )
        db.add(user)
        db.flush()
        try:
            await send_verification_email(email, body.isp_name, token)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail="Verification email could not be sent. Try again later") from exc
        db.commit()
        return {"status": "verification_required", "email": email}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    finally:
        db.close()


@router.post("/verify-email")
async def verify_email(body: EmailVerificationRequest):
    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.email_verification_token_hash == hash_token(body.token)).first()
        now = datetime.utcnow()
        if user is None or user.email_verification_expires_at is None or user.email_verification_expires_at < now:
            raise HTTPException(status_code=400, detail="This verification link is invalid or has expired")
        user.email_verified_at = now
        user.email_verification_token_hash = None
        user.email_verification_expires_at = None
        user.email_verification_sent_at = None
        user.is_active = True
        user.token_version += 1
        db.commit()
        db.refresh(user)
        return _issue_access_token(user)
    finally:
        db.close()


@router.post("/resend-verification", status_code=202)
async def resend_verification(body: ResendVerificationRequest):
    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(func.lower(AdminUser.email) == body.email.lower()).first()
        if user is None or user.email_verified_at is not None:
            return {"status": "ok"}

        now = datetime.utcnow()
        if user.email_verification_sent_at and (now - user.email_verification_sent_at).total_seconds() < _resend_seconds():
            raise HTTPException(status_code=429, detail="A verification email was sent recently. Try again shortly")

        token = random_token()
        user.email_verification_token_hash = hash_token(token)
        user.email_verification_expires_at = now + timedelta(minutes=_verification_minutes())
        user.email_verification_sent_at = now
        db.flush()
        try:
            await send_verification_email(user.email, user.isp_name or "ISP operator", token)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail="Verification email could not be sent. Try again later") from exc
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        user = _find_login_user(db, form_data.username.strip())
        candidate_hash = user.hashed_password if user else DUMMY_HASH
        valid = pwd_context.verify(form_data.password, candidate_hash)
        if user and user.locked_until and user.locked_until > now and not valid:
            raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later")
        if user is None or not valid:
            if user:
                user.failed_login_count += 1
                if user.failed_login_count >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    user.failed_login_count = 0
                db.commit()
            raise HTTPException(status_code=401, detail="Incorrect email, username or password", headers={"WWW-Authenticate": "Bearer"})
        if not user.is_active:
            if user.email and user.email_verified_at is None:
                raise HTTPException(status_code=403, detail="Verify your email before signing in")
            raise HTTPException(status_code=403, detail="Account is disabled")
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        db.commit()
        return _issue_access_token(user)
    finally:
        db.close()
