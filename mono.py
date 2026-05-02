import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel

from database import crud
from database.models import AdminUser
from database.session import SessionLocal
from services.active_users_service import get_hotspot_active_users, get_ppp_active_users
from services.hotspot_service import create_hotspot_user, get_hotspot_users
from services.logs_service import create_log, get_logs
from services.mikrotik_service import fetch_rt_rx_tx_data
from services.package_service import create_package, get_packages
from services.payment_service import (
    get_payments,
    get_payments_by_user_type,
    get_total_payment_by_user_type,
    get_total_payment_for_today_by_user_type,
    initiate_stk_push,
)
from services.ppp_service import create_ppp_user, get_ppp_users
from services.router_service import create_router, get_routers, ping_routers

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _get_current_user(token: str = Depends(oauth2_scheme)) -> AdminUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_id(db, int(user_id))
    finally:
        db.close()

    if user is None or not user.is_active:
        raise credentials_error
    return user


def _validate_router_access(router_id: int, current_user: AdminUser) -> None:
    """Raise 403 if router_id does not belong to the current user (superadmin bypasses)."""
    if current_user.role == "superadmin":
        return
    db = SessionLocal()
    try:
        router = crud.get_router_by_id(db, router_id)
    finally:
        db.close()
    if router is None or router.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this router")


def _require_superadmin(current_user: AdminUser = Depends(_get_current_user)) -> AdminUser:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


# ---------------------------------------------------------------------------
# Startup: seed superadmin from env (SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD)
# ---------------------------------------------------------------------------
def _seed_superadmin() -> None:
    sa_username = os.getenv("SUPERADMIN_USERNAME")
    sa_password = os.getenv("SUPERADMIN_PASSWORD")
    if not sa_username or not sa_password:
        return
    db = SessionLocal()
    try:
        if crud.get_admin_user_by_username(db, sa_username) is None:
            hashed = pwd_context.hash(sa_password)
            crud.create_admin_user(db, username=sa_username, hashed_password=hashed, role="superadmin")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "isp"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(redirect_slashes=False, on_startup=[_seed_superadmin])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth endpoint
# ---------------------------------------------------------------------------
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_username(db, form_data.username)
    finally:
        db.close()

    if user is None or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    token = jwt.encode({"sub": str(user.id), "role": user.role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# User management (superadmin only)
# ---------------------------------------------------------------------------
@app.post("/users")
async def create_user_endpoint(
    body: CreateUserRequest,
    _sa: AdminUser = Depends(_require_superadmin),
):
    if body.role not in ("superadmin", "isp"):
        raise HTTPException(status_code=400, detail="role must be 'superadmin' or 'isp'")
    db = SessionLocal()
    try:
        if crud.get_admin_user_by_username(db, body.username):
            raise HTTPException(status_code=409, detail="Username already exists")
        hashed = pwd_context.hash(body.password)
        user = crud.create_admin_user(db, username=body.username, hashed_password=hashed, role=body.role, email=body.email)
        return {"id": user.id, "username": user.username, "role": user.role, "email": user.email}
    finally:
        db.close()


@app.get("/users")
async def list_users_endpoint(_sa: AdminUser = Depends(_require_superadmin)):
    db = SessionLocal()
    try:
        users = crud.list_admin_users(db)
        return [{"id": u.id, "username": u.username, "role": u.role, "email": u.email, "is_active": u.is_active} for u in users]
    finally:
        db.close()


@app.post("/users/change-password")
async def change_password_endpoint(
    body: ChangePasswordRequest,
    current_user: AdminUser = Depends(_get_current_user),
):
    if not pwd_context.verify(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db = SessionLocal()
    try:
        user = crud.get_admin_user_by_id(db, current_user.id)
        user.hashed_password = pwd_context.hash(body.new_password)
        db.commit()
    finally:
        db.close()
    return {"detail": "Password updated successfully"}


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------
@app.post("/router")
async def create_router_endpoint(
    name: str,
    ip_address: str,
    password: str,
    port: int = 8728,
    username: str = "admin",
    current_user: AdminUser = Depends(_get_current_user),
):
    try:
        return create_router(name, ip_address, port, username, password, owner_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/routers")
async def get_routers_endpoint(current_user: AdminUser = Depends(_get_current_user)):
    try:
        owner_id = None if current_user.role == "superadmin" else current_user.id
        return get_routers(owner_id=owner_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/routers/ping")
async def ping_routers_endpoint(
    router_id: Optional[int] = None,
    current_user: AdminUser = Depends(_get_current_user),
):
    if router_id is not None:
        _validate_router_access(router_id, current_user)
    try:
        owner_id = None if current_user.role == "superadmin" else current_user.id
        owned_ids = None if owner_id is None else [r["id"] for r in get_routers(owner_id=owner_id)]
        return ping_routers(router_id=router_id, allowed_ids=owned_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Package endpoints
# ---------------------------------------------------------------------------
@app.post("/package")
async def create_package_endpoint(
    name: str,
    description: str,
    price: float,
    service_type: str,
    validity_days: int,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return create_package(name, description, price, service_type, validity_days, router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/packages")
async def get_packages_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_packages(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Payment endpoints
# ---------------------------------------------------------------------------
@app.get("/payments")
async def get_payments_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_payments(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/payments/{user_type}")
async def get_payments_by_user_type_endpoint(
    user_type: str,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_payments_by_user_type(user_type, router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/payments/total/{user_type}")
async def get_total_payment_by_user_type_endpoint(
    user_type: str,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return {"total_payment": get_total_payment_by_user_type(user_type, router_id=router_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/payments/today/total/{user_type}")
async def get_today_total_payment_by_user_type_endpoint(
    user_type: str,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return {"total_payment": get_total_payment_for_today_by_user_type(user_type, router_id=router_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Hotspot user endpoints
# ---------------------------------------------------------------------------
@app.get("/hotspot_users")
async def get_hotspot_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_hotspot_users(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/hotspot_users/active")
async def get_hotspot_active_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_hotspot_active_users(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/hotspot_user")
async def create_hotspot_user_endpoint(
    phone_number: str,
    amount: int,
    otp: str,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return create_hotspot_user(phone_number, amount, otp, router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# PPP user endpoints
# ---------------------------------------------------------------------------
@app.get("/ppp_users")
async def get_ppp_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_ppp_users(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ppp_users/active")
async def get_ppp_active_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_ppp_active_users(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ppp_user")
async def create_ppp_user_endpoint(
    name: str,
    email: str,
    pppoe_username: str,
    pppoe_password: str,
    mobile_number: str,
    location: str,
    apartment: str,
    profile: str,
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return create_ppp_user(name, email, pppoe_username, pppoe_password, mobile_number, location, apartment, profile, router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------
@app.get("/logs")
async def get_logs_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return get_logs(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/log")
async def create_log_endpoint(
    description: str,
    router_id: int,
    phone_number: Optional[str] = None,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return create_log(description, phone_number, router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# MikroTik data endpoints
# ---------------------------------------------------------------------------
@app.get("/rt_rx_data")
async def fetch_rt_rx_data_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        return fetch_rt_rx_tx_data(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/active_users/{router_id}/hotspot")
async def get_active_hotspot_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        hotspot_active = get_hotspot_active_users(router_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "router_id": router_id,
        "generated_at": datetime.utcnow().isoformat(),
        "hotspot_active": hotspot_active,
    }


@app.get("/active_users/{router_id}/pppoe")
async def get_active_pppoe_users_endpoint(
    router_id: int,
    current_user: AdminUser = Depends(_get_current_user),
):
    _validate_router_access(router_id, current_user)
    try:
        pppoe_active = get_ppp_active_users(router_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "router_id": router_id,
        "generated_at": datetime.utcnow().isoformat(),
        "pppoe_active": pppoe_active,
    }


# ---------------------------------------------------------------------------
# STK Push (auth-protected, router ownership validated)
# ---------------------------------------------------------------------------
@app.post("/stkpush/initiate")
async def initiate_stk_push_endpoint(
    phone_number: str,
    amount: int,
    router_id: int,
):
    try:
        return await initiate_stk_push(phone_number, amount, router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# To run: uvicorn mono:app --host 0.0.0.0 --port 8000 --reload
