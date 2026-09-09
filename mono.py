"""Uzanet ISP control-plane API.

Run with ``gunicorn mono:app -k uvicorn.workers.UvicornWorker``. All business APIs live
under /api/v1. The unversioned /token alias is retained only for a safe rolling frontend
deployment; the legacy public STK endpoint is intentionally retired.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from database import crud
from database.models import AdminUser, HotspotUser, Package, PPPUser
from database.session import SessionLocal
from schemas import (
    ChangePasswordRequest,
    CreateAdminUserRequest,
    HotspotUserCreateRequest,
    PackageCreateRequest,
    PackageUpdateRequest,
    PPPUserCreateRequest,
    PublicPaymentRequest,
    RouterClaimRequest,
    RouterCreateRequest,
    RouterOnboardingRequest,
    RouterUpdateRequest,
)
from security import mask_phone
from services.access_service import (
    create_hotspot_customer,
    create_pppoe_customer,
    delete_customer,
    list_hotspot_users,
    list_pppoe_users,
    set_customer_enabled,
)
from services.active_users_service import get_hotspot_active_users, get_ppp_active_users
from services.maintenance_service import expire_access
from services.mikrotik_service import fetch_rt_rx_tx_data
from services.onboarding_service import claim_onboarding, create_onboarding, consume_onboarding_script
from services.package_service import create_package, list_packages, retire_package, update_package
from services.payment_providers import (
    kopokopo_callback_values,
    mpesa_callback_values,
    verify_kopokopo_signature,
)
from services.payment_service import (
    create_public_payment,
    get_public_payment,
    list_payment_sessions,
    list_payments,
    process_kopokopo_callback,
    process_mpesa_callback,
    public_portal,
    retry_provisioning,
)
from services.router_service import (
    check_all_routers,
    check_router,
    create_router,
    delete_router,
    encrypt_legacy_credentials,
    get_router_for_user,
    list_routers,
    update_router,
)
from settings import get_settings


logger = logging.getLogger("uzanet.api")
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def _seed_superadmin() -> None:
    username = __import__("os").getenv("SUPERADMIN_USERNAME")
    password = __import__("os").getenv("SUPERADMIN_PASSWORD")
    db = SessionLocal()
    try:
        # Deactivate historical known-default accounts if their passwords were never changed.
        for legacy_username, legacy_password in (("admin", "secret"), ("superadmin", "admin123")):
            legacy = crud.get_admin_user_by_username(db, legacy_username)
            try:
                uses_default = bool(legacy and pwd_context.verify(legacy_password, legacy.hashed_password))
            except (TypeError, ValueError):
                uses_default = False
            if uses_default:
                legacy.is_active = False
                legacy.token_version += 1
                logger.warning("Deactivated historical default account: %s", legacy_username)
        db.commit()
        if username and password and crud.get_admin_user_by_username(db, username) is None:
            if len(password) < 12:
                raise RuntimeError("SUPERADMIN_PASSWORD must contain at least 12 characters")
            try:
                crud.create_admin_user(db, username=username, hashed_password=pwd_context.hash(password), role="superadmin")
            except IntegrityError:
                # Another application worker may have completed the same first-boot seed.
                db.rollback()
                if crud.get_admin_user_by_username(db, username) is None:
                    raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate()
    _seed_superadmin()
    converted = encrypt_legacy_credentials()
    if converted:
        logger.warning("Encrypted %s legacy router credential(s)", converted)
    yield


app = FastAPI(
    title="Uzanet ISP API",
    version="1.0.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Payment-Token", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")
    if len(request_id) > 64 or not request_id.replace("-", "").isalnum():
        request_id = ""
    request_id = request_id or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    if "/onboarding" in request.url.path or "/router-onboarding/" in request.url.path:
        response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https" or settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error request_id=%s", request.state.request_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request.state.request_id},
    )


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> AdminUser:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience="uzanet-admin",
            issuer="uzanet-api",
            options={"require": ["sub", "exp", "iat", "jti", "ver"]},
        )
        user_id = int(payload["sub"])
        token_version = int(payload["ver"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise _credentials_error() from exc
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_id(db, user_id)
        if user is None or not user.is_active or user.token_version != token_version:
            raise _credentials_error()
        db.expunge(user)
        return user
    finally:
        db.close()


def require_superadmin(current_user: AdminUser = Depends(get_current_user)) -> AdminUser:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


def _authenticate(form_data: OAuth2PasswordRequestForm) -> dict:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_username(db, form_data.username)
        # Always verify a hash to reduce username-enumeration timing differences.
        candidate_hash = user.hashed_password if user else "$2b$12$2b2xVQyQmD/3C7Y62A/BKuF7VL2NfFv.i3I9qLfVFe1qgD0uYPZZK"
        valid = pwd_context.verify(form_data.password, candidate_hash)
        if user and user.locked_until and user.locked_until > now:
            raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later")
        if user is None or not valid:
            if user:
                user.failed_login_count += 1
                if user.failed_login_count >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    user.failed_login_count = 0
                db.commit()
            raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        db.commit()
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
        return {"access_token": encoded, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60}
    finally:
        db.close()


async def _router_call(function, *args):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(function, *args),
            timeout=settings.router_operation_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Router operation timed out") from exc


@app.get("/health/live", include_in_schema=False)
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def health_ready():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    finally:
        db.close()


@app.post("/api/v1/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    return _authenticate(form_data)


@app.post("/token", include_in_schema=False)
async def legacy_login(form_data: OAuth2PasswordRequestForm = Depends()):
    return _authenticate(form_data)


@app.get("/api/v1/me")
async def me(current_user: AdminUser = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email, "role": current_user.role}


@app.post("/api/v1/auth/logout", status_code=204)
async def logout(current_user: AdminUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_id(db, current_user.id)
        user.token_version += 1
        db.commit()
    finally:
        db.close()
    return Response(status_code=204)


@app.post("/api/v1/users", status_code=201)
async def create_admin_user(body: CreateAdminUserRequest, _sa: AdminUser = Depends(require_superadmin)):
    db = SessionLocal()
    try:
        if crud.get_admin_user_by_username(db, body.username):
            raise HTTPException(status_code=409, detail="Username already exists")
        user = crud.create_admin_user(db, body.username, pwd_context.hash(body.password), body.role, body.email)
        return {"id": user.id, "username": user.username, "email": user.email, "role": user.role, "is_active": user.is_active}
    finally:
        db.close()


@app.get("/api/v1/users")
async def list_admin_users(_sa: AdminUser = Depends(require_superadmin)):
    db = SessionLocal()
    try:
        return [{"id": row.id, "username": row.username, "email": row.email, "role": row.role, "is_active": row.is_active} for row in crud.list_admin_users(db)]
    finally:
        db.close()


@app.post("/api/v1/users/change-password", status_code=204)
async def change_password(body: ChangePasswordRequest, current_user: AdminUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_id(db, current_user.id)
        if not pwd_context.verify(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.hashed_password = pwd_context.hash(body.new_password)
        user.token_version += 1
        db.commit()
    finally:
        db.close()
    return Response(status_code=204)


@app.get("/api/v1/routers")
async def routers(current_user: AdminUser = Depends(get_current_user)):
    return list_routers(current_user)


@app.post("/api/v1/routers", status_code=201)
async def add_router(body: RouterCreateRequest, current_user: AdminUser = Depends(get_current_user)):
    return create_router(body, current_user)


@app.patch("/api/v1/routers/{router_uid}")
async def edit_router(router_uid: str, body: RouterUpdateRequest, current_user: AdminUser = Depends(get_current_user)):
    return update_router(router_uid, body, current_user)


@app.delete("/api/v1/routers/{router_uid}", status_code=204)
async def remove_router(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    delete_router(router_uid, current_user)
    return Response(status_code=204)


@app.get("/api/v1/routers/status")
async def routers_status(current_user: AdminUser = Depends(get_current_user)):
    return await _router_call(check_all_routers, current_user)


@app.get("/api/v1/routers/{router_uid}/status")
async def one_router_status(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return await _router_call(check_router, router_uid, current_user)


@app.post("/api/v1/routers/onboarding", status_code=201)
async def begin_onboarding(body: RouterOnboardingRequest, current_user: AdminUser = Depends(get_current_user)):
    return create_onboarding(body, current_user)


@app.get("/api/v1/router-onboarding/{router_uid}/script", response_class=Response)
def download_onboarding_script(router_uid: uuid.UUID, x_onboarding_token: str = Header(default="")):
    script = consume_onboarding_script(str(router_uid), x_onboarding_token)
    return Response(script, media_type="text/plain", headers={
        "Content-Disposition": f'attachment; filename="uzanet-{router_uid}.rsc"',
        "Cache-Control": "no-store, private",
    })


@app.post("/api/v1/router-onboarding/claim")
async def claim_router(body: RouterClaimRequest):
    return claim_onboarding(body.token, body.tunnel_ip, body.routeros_version)


@app.get("/api/v1/routers/{router_uid}/packages")
async def packages(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return list_packages(get_router_for_user(router_uid, current_user))


@app.post("/api/v1/routers/{router_uid}/packages", status_code=201)
async def add_package(router_uid: str, body: PackageCreateRequest, current_user: AdminUser = Depends(get_current_user)):
    return create_package(get_router_for_user(router_uid, current_user), body)


@app.patch("/api/v1/routers/{router_uid}/packages/{package_uid}")
async def edit_package(router_uid: str, package_uid: str, body: PackageUpdateRequest, current_user: AdminUser = Depends(get_current_user)):
    return update_package(get_router_for_user(router_uid, current_user), package_uid, body)


@app.delete("/api/v1/routers/{router_uid}/packages/{package_uid}")
async def remove_package(router_uid: str, package_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return retire_package(get_router_for_user(router_uid, current_user), package_uid)


@app.get("/api/v1/routers/{router_uid}/hotspot-users")
async def hotspot_users(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return list_hotspot_users(get_router_for_user(router_uid, current_user))


@app.post("/api/v1/routers/{router_uid}/hotspot-users", status_code=201)
async def add_hotspot_user(router_uid: str, body: HotspotUserCreateRequest, current_user: AdminUser = Depends(get_current_user)):
    router = get_router_for_user(router_uid, current_user)
    return await _router_call(create_hotspot_customer, router, body)


@app.post("/api/v1/routers/{router_uid}/hotspot-users/{user_uid}/{action}")
async def hotspot_user_action(router_uid: str, user_uid: str, action: str, current_user: AdminUser = Depends(get_current_user)):
    if action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="Action not found")
    router = get_router_for_user(router_uid, current_user)
    return await _router_call(set_customer_enabled, router, "hotspot", user_uid, action == "enable")


@app.delete("/api/v1/routers/{router_uid}/hotspot-users/{user_uid}", status_code=204)
async def remove_hotspot_user(router_uid: str, user_uid: str, current_user: AdminUser = Depends(get_current_user)):
    await _router_call(delete_customer, get_router_for_user(router_uid, current_user), "hotspot", user_uid)
    return Response(status_code=204)


@app.get("/api/v1/routers/{router_uid}/pppoe-users")
async def pppoe_users(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return list_pppoe_users(get_router_for_user(router_uid, current_user))


@app.post("/api/v1/routers/{router_uid}/pppoe-users", status_code=201)
async def add_pppoe_user(router_uid: str, body: PPPUserCreateRequest, current_user: AdminUser = Depends(get_current_user)):
    router = get_router_for_user(router_uid, current_user)
    return await _router_call(create_pppoe_customer, router, body)


@app.post("/api/v1/routers/{router_uid}/pppoe-users/{user_uid}/{action}")
async def pppoe_user_action(router_uid: str, user_uid: str, action: str, current_user: AdminUser = Depends(get_current_user)):
    if action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="Action not found")
    router = get_router_for_user(router_uid, current_user)
    return await _router_call(set_customer_enabled, router, "pppoe", user_uid, action == "enable")


@app.delete("/api/v1/routers/{router_uid}/pppoe-users/{user_uid}", status_code=204)
async def remove_pppoe_user(router_uid: str, user_uid: str, current_user: AdminUser = Depends(get_current_user)):
    await _router_call(delete_customer, get_router_for_user(router_uid, current_user), "pppoe", user_uid)
    return Response(status_code=204)


@app.get("/api/v1/routers/{router_uid}/active-users")
async def active_users(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    router = get_router_for_user(router_uid, current_user)
    hotspot, pppoe = await asyncio.gather(
        _router_call(get_hotspot_active_users, router.id),
        _router_call(get_ppp_active_users, router.id),
    )
    return {"router_uid": router.uid, "generated_at": datetime.utcnow(), "hotspot": hotspot, "pppoe": pppoe}


@app.get("/api/v1/routers/{router_uid}/traffic")
async def traffic(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    router = get_router_for_user(router_uid, current_user)
    return await _router_call(fetch_rt_rx_tx_data, router.id)


@app.get("/api/v1/routers/{router_uid}/payments")
async def payments(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return list_payments(get_router_for_user(router_uid, current_user))


@app.get("/api/v1/routers/{router_uid}/payment-sessions")
async def payment_sessions(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    return list_payment_sessions(get_router_for_user(router_uid, current_user))


@app.get("/api/v1/routers/{router_uid}/logs")
async def logs(router_uid: str, current_user: AdminUser = Depends(get_current_user)):
    router = get_router_for_user(router_uid, current_user)
    db = SessionLocal()
    try:
        return [
            {
                "id": row.id,
                "timestamp": row.timestamp,
                "level": row.level,
                "event_type": row.event_type,
                "description": row.description,
                "phone_number": mask_phone(row.phone_number) if row.phone_number else None,
            }
            for row in crud.get_logs(db, router.id)
        ]
    finally:
        db.close()


@app.post("/api/v1/payments/{payment_id}/retry-provisioning")
async def retry_payment_provisioning(payment_id: str, current_user: AdminUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        session = crud.get_payment_session_by_public_id(db, payment_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Payment session not found")
        router = crud.get_router_by_id(db, session.router_id)
        if current_user.role != "superadmin" and router.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Payment session not found")
    finally:
        db.close()
    return await _router_call(retry_provisioning, payment_id)


@app.post("/api/v1/jobs/expire-access")
async def run_expiry_job(_sa: AdminUser = Depends(require_superadmin)):
    return await _router_call(expire_access)


@app.get("/api/v1/public/portals/{portal_slug}")
async def portal(portal_slug: str):
    return public_portal(portal_slug)


@app.post("/api/v1/public/portals/{portal_slug}/payments", status_code=202)
async def start_public_payment(
    portal_slug: str,
    body: PublicPaymentRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
):
    return await create_public_payment(portal_slug, body, idempotency_key, request.client.host if request.client else None)


@app.get("/api/v1/public/payments/{payment_id}")
async def payment_status(payment_id: str, status_token: str = Header(..., alias="X-Payment-Token")):
    return get_public_payment(payment_id, status_token)


@app.post("/api/v1/webhooks/mpesa/stk", status_code=204)
async def mpesa_webhook(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    await process_mpesa_callback(mpesa_callback_values(payload))
    return Response(status_code=204)


@app.post("/api/v1/webhooks/kopokopo/incoming-payment", status_code=204)
async def kopokopo_webhook(request: Request, signature: str | None = Header(None, alias="X-KopoKopo-Signature")):
    raw = await request.body()
    if not verify_kopokopo_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    await _router_call(process_kopokopo_callback, kopokopo_callback_values(payload))
    return Response(status_code=204)


@app.post("/stkpush/initiate", include_in_schema=False)
async def retired_legacy_stk():
    raise HTTPException(status_code=410, detail="Use the portal-scoped payment API")
