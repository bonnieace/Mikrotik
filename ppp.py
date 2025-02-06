import asyncio
import os
import random
import string
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from librouteros import connect
from librouteros.exceptions import TrapError
from pydantic import BaseModel
import httpx

# Load environment variables
load_dotenv()

# MikroTik connection details
MIKROTIK_HOST = os.getenv("MIKROTIK_HOST")
MIKROTIK_PORT = int(os.getenv("MIKROTIK_PORT"))
MIKROTIK_USER = os.getenv("MIKROTIK_USER")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD")

# M-PESA credentials
BASE_URL = "https://sandbox.safaricom.co.ke"
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")

# FastAPI instance
app = FastAPI()

# Pydantic models
class PPPClient(BaseModel):
    username: str
    password: str
    profile: str = "default"
    service: str = "pppoe"

class RenewalRequest(BaseModel):
    username: str
    amount: int  # Payment amount


# Utility function to connect to MikroTik
def connect_to_router():
    try:
        return connect(
            username=MIKROTIK_USER,
            password=MIKROTIK_PASSWORD,
            host=MIKROTIK_HOST,
            port=MIKROTIK_PORT,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


# Add PPP Client
@app.post("/ppp/add")
def add_ppp_client(client: PPPClient):
    try:
        api = connect_to_router()
        ppp_users = api.path("ppp", "secret")
        ppp_users.add(
            name=client.username,
            password=client.password,
            profile=client.profile,
            service=client.service,
        )
        return {"message": f"PPP client '{client.username}' added successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error adding PPP client: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Process Renewal
@app.post("/ppp/renew")
async def renew_ppp_client(request: RenewalRequest):
    # Step 1: Generate M-PESA OAuth Token
    auth_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
        if auth_response.status_code != 200:
            raise HTTPException(
                status_code=auth_response.status_code, detail="Failed to generate access token"
            )
        access_token = auth_response.json().get("access_token")

    # Step 2: Validate Payment
    stk_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": "174379",
        "Password": "BASE64_ENCODED_PASSWORD",  # Replace with generated password
        "Timestamp": "CURRENT_TIMESTAMP",  # Replace with timestamp
        "CheckoutRequestID": "CHECKOUT_REQUEST_ID",  # Replace with valid ID
    }

    async with httpx.AsyncClient() as client:
        query_response = await client.post(stk_url, json=payload, headers=headers)

    if query_response.status_code != 200:
        raise HTTPException(status_code=query_response.status_code, detail="Payment validation failed")

    payment_status = query_response.json().get("ResultCode")
    if payment_status != "0":
        raise HTTPException(status_code=400, detail="Payment unsuccessful or pending")

    # Step 3: Update PPP Client Limit
    try:
        api = connect_to_router()
        ppp_users = api.path("ppp", "secret")

        # Determine new limit based on payment amount
        uptime_mapping = {10: "1h", 50: "1d", 150: "3d", 300: "1w", 1000: "4w"}
        new_uptime = uptime_mapping.get(request.amount)
        if not new_uptime:
            raise HTTPException(status_code=400, detail="Invalid payment amount")

        # Update user's limit
        for user in ppp_users:
            if user.get("name") == request.username:
                ppp_users.update(user, **{"limit-uptime": new_uptime})
                return {"message": f"PPP client '{request.username}' renewed successfully"}

        raise HTTPException(status_code=404, detail="PPP client not found")
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error renewing PPP client: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
# List PPP Clients
@app.get("/ppp/clients")
def list_ppp_clients():
    try:
        # Connect to MikroTik router
        api = connect_to_router()
        ppp_users = api.path("ppp", "secret")
        
        # Retrieve all PPP clients
        clients = [
            {
                "username": user.get("name"),
                "profile": user.get("profile"),
                "service": user.get("service"),
            
            }
            for user in ppp_users
        ]

        # Return the client list
        return {"clients": clients}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving PPP clients: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# List PPP active Clients
@app.get("/ppp/clients/active")
def list_ppp_clients():
    try:
        # Connect to MikroTik router
        api = connect_to_router()
        ppp_users = api.path("ppp", "active")
        
        # Retrieve all PPP clients
        clients = [
            {
                "username": user.get("name"),
                "profile": user.get("profile"),
                "service": user.get("service"),
            
            }
            for user in ppp_users
        ]

        # Return the client list
        return {"clients": clients}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving PPP clients: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
        
# List available PPP profiles
@app.get("/ppp/profiles")
def list_ppp_profiles():
    try:
        # Connect to MikroTik router
        api = connect_to_router()
        ppp_profiles = api.path("ppp", "profile")
        
        # Retrieve all profiles
        profiles = [
            {
                "name": profile.get("name"),
                "rate_limit": profile.get("rate-limit"),
                "local_address": profile.get("local-address"),
                "remote_address": profile.get("remote-address"),
            }
            for profile in ppp_profiles
        ]

        # Return the profiles list
        return {"profiles": profiles}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving PPP profiles: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Add a PPP profile
@app.post("/ppp/profiles")
def add_ppp_profile(
    name: str, 
    rate_limit: str = None, 
    local_address: str = None, 
    remote_address: str = None
):
    try:
        # Connect to MikroTik router
        api = connect_to_router()
        
        # Add a new profile
        api.path("ppp", "profile").add(
            name=name, 
            **({"rate-limit": rate_limit} if rate_limit else {}),
            **({"local-address": local_address} if local_address else {}),
            **({"remote-address": remote_address} if remote_address else {})
        )
        
        return {"message": f"PPP profile '{name}' successfully added."}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error adding PPP profile: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
@app.post("/ppp/clients/login")
def ppp_client_login(name: str, password: str):
    try:
        api = connect_to_router()
        ppp_clients = api.path("ppp", "secret")

        # Find the client by name
        client = next(
            (entry for entry in ppp_clients if entry.get("name") == name), 
            None
        )

        if not client:
            raise HTTPException(status_code=404, detail=f"PPP client '{name}' not found.")
        
        # Check if the password matches
        if client["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid request.")

        return {"message": f"PPP client '{name}' successfully logged in."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
