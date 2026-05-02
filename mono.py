from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
import jwt

from services.active_users_service import get_hotspot_active_users, get_ppp_active_users
from services.hotspot_service import create_hotspot_user, get_hotspot_users
from services.logs_service import create_log, get_logs
from services.mikrotik_service import fetch_rt_rx_tx_data
from services.payment_service import (
    get_payments,
    get_payments_by_user_type,
    get_total_payment_by_user_type,
    get_total_payment_for_today_by_user_type,
    initiate_stk_push
)
from services.package_service import create_package, get_packages
from services.ppp_service import create_ppp_user, get_ppp_users
from services.router_service import create_router, get_routers, ping_routers

# --- Configuration for OAuth2 JWT Authentication ---
SECRET_KEY = "your-secret-key"  # TODO: move to environment variable or secure vault
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

async def authenticate(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# --- FastAPI Application Setup ---
app = FastAPI(redirect_slashes=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Public Endpoints ---
@app.post("/stkpush/initiate")
async def initiate_stk_push_endpoint(phone_number: str, amount: int, router_id: int):
    try:
        return await initiate_stk_push(phone_number, amount, router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Token endpoint for Swagger UI
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # TODO: Replace with real user credential verification
    if form_data.username != "admin" or form_data.password != "secret":
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    expire = datetime.utcnow() + timedelta(hours=1)
    token_payload = {"sub": form_data.username, "exp": expire}
    token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

# --- Protected Endpoints (Swagger UI will show lock icon) ---
@app.post("/package", dependencies=[Depends(authenticate)])
async def create_package_endpoint(
    name: str,
    description: str,
    price: float,
    service_type: str,
    validity_days: int
):
    try:
        return create_package(name, description, price, service_type, validity_days)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/packages", dependencies=[Depends(authenticate)])
async def get_packages_endpoint():
    try:
        return get_packages()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/payments", dependencies=[Depends(authenticate)])
async def get_payments_endpoint():
    try:
        return get_payments()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/payments/{user_type}", dependencies=[Depends(authenticate)])
async def get_payments_by_user_type_endpoint(user_type: str):
    try:
        return get_payments_by_user_type(user_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/payments/total/{user_type}", dependencies=[Depends(authenticate)])
async def get_total_payment_by_user_type_endpoint(user_type: str):
    try:
        return {"total_payment": get_total_payment_by_user_type(user_type)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/hotspot_users", dependencies=[Depends(authenticate)])
async def get_hotspot_users_endpoint(router_id: Optional[int] = None):
    try:
        return get_hotspot_users(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/logs", dependencies=[Depends(authenticate)])
async def get_logs_endpoint():
    try:
        return get_logs()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/log", dependencies=[Depends(authenticate)])
async def create_log_endpoint(description: str, phone_number: str = None, router_id: int = None):
    try:
        return create_log(description, phone_number, router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ppp_user", dependencies=[Depends(authenticate)])
async def create_ppp_user_endpoint(
    name: str,
    email: str,
    pppoe_username: str,
    pppoe_password: str,
    mobile_number: str,
    location: str,
    apartment: str,
    profile: str,
    router_id: int
):
    try:
        return create_ppp_user(
            name, email, pppoe_username, pppoe_password,
            mobile_number, location, apartment, profile, router_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ppp_users", dependencies=[Depends(authenticate)])
async def get_ppp_users_endpoint(router_id: Optional[int] = None):
    try:
        return get_ppp_users(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/hotspot_user", dependencies=[Depends(authenticate)])
async def create_hotspot_user_endpoint(phone_number: str, amount: int, otp: str, router_id: int):
    try:
        return create_hotspot_user(phone_number, amount, otp, router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/rt_rx_data", dependencies=[Depends(authenticate)])
async def fetch_rt_rx_data_endpoint(router_id: int):
    try:
        return fetch_rt_rx_tx_data(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/payments/today/total/{user_type}", dependencies=[Depends(authenticate)])
async def get_today_total_payment_by_user_type_endpoint(user_type: str):
    try:
        return {"total_payment": get_total_payment_for_today_by_user_type(user_type)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/router", dependencies=[Depends(authenticate)])
async def create_router_endpoint(
    name: str,
    ip_address: str,
    password: str,
    port: int = 8728,
    username: str = "admin",
):
    try:
        return create_router(name, ip_address, port, username, password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/routers", dependencies=[Depends(authenticate)])
async def get_routers_endpoint():
    try:
        return get_routers()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/routers/ping", dependencies=[Depends(authenticate)])
async def ping_routers_endpoint(router_id: Optional[int] = None):
    try:
        return ping_routers(router_id=router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/hotspot_users/active", dependencies=[Depends(authenticate)])
async def get_hotspot_active_users_endpoint(router_id: int):
    try:
        return get_hotspot_active_users(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ppp_users/active", dependencies=[Depends(authenticate)])
async def get_ppp_active_users_endpoint(router_id: int):
    try:
        return get_ppp_active_users(router_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/active_users/{router_id}/hotspot", dependencies=[Depends(authenticate)])
async def get_active_hotspot_users_endpoint(router_id: int):
    """Return currently active hotspot sessions from the specified router."""
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


@app.get("/active_users/{router_id}/pppoe", dependencies=[Depends(authenticate)])
async def get_active_pppoe_users_endpoint(router_id: int):
    """Return currently active PPPoE sessions from the specified router."""
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

# To run: uvicorn mono:app --host 0.0.0.0 --port 8000 --reload
