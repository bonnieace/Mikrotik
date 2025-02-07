import asyncio
from fastapi import FastAPI, HTTPException
from librouteros import connect
from librouteros.exceptions import TrapError
import random
import string
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import time

# Load environment variables
load_dotenv()

# MikroTik connection details
MIKROTIK_HOST = os.getenv("MIKROTIK_HOST")
MIKROTIK_PORT = int(os.getenv("MIKROTIK_PORT"))
MIKROTIK_USER = os.getenv("MIKROTIK_USER")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD")

# FastAPI app
app = FastAPI()

# Pydantic models for request bodies
class User(BaseModel):
    name: str
    password: str
    group: str = 'read'

class ModifyUser(BaseModel):
    password: str = None
    group: str = None
    disabled: bool = None

class VoucherRequest(BaseModel):
    profile: str
    count: int = 1
    duration: str  # e.g., "1h", "1d", "1w"

class HotspotUserRequest(BaseModel):
    name: str
    password: str
    profile: str
    limit_uptime: str  # e.g., "1h", "1d", "1w"
    #address: str = None  # Optional, depending on your requirements


# Utility function to connect to the router
def connect_to_router():
    try:
        api = connect(
            username=MIKROTIK_USER,
            password=MIKROTIK_PASSWORD,
            host=MIKROTIK_HOST,
            port=MIKROTIK_PORT
        )
        return api
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

# Endpoints

app.mount("/hotspot", StaticFiles(directory="hotspot"), name="hotspot")
origins = [
    "*",  # Replace with the origin of your frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

# Safaricom API credentials
BASE_URL = "https://sandbox.safaricom.co.ke"
CONSUMER_KEY = "YJwAugvyRWklll798WT0CRP60IlaC4GsmXaDaG3tESRzJzfF"
CONSUMER_SECRET = "ouz2P5YwOAKoRBnyJj8UVAIS8fZhqALYTM5NrUDG0Pu5Y5L8KdYw8z0TcFzdI0Nn"
@app.post("/callback")

async def mpesa_callback(data: dict):
    callback_body = data.get("Body", {}).get("stkCallback", {})
    result_code = callback_body.get("ResultCode")
    result_desc = callback_body.get("ResultDesc")
    metadata = callback_body.get("CallbackMetadata", {}).get("Item", [])
    
    if result_code == 0:
        print("Payment successful:", metadata)
        # Store or process the payment details here
    else:
        print("Payment failed:", result_desc)
    
    return {"status": "processed"}

@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

@app.get("/hotspot/redirect")
async def serve_redirect_html():
    """
    Serve the HTML file located at hotspot/redirect/index.html.
    """
    file_path = "hotspot/redirect/login.html"
    return FileResponse(file_path)

@app.post("/stkpush/initiate")
async def initiate_stk_push(phone_number: str, amount: int):
    # Generate OAuth token
    auth_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    if auth_response.status_code != 200:
        raise HTTPException(status_code=auth_response.status_code, detail="Failed to generate access token")
    
    access_token = auth_response.json().get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token missing in response")
    
    # Initiate STK Push
    stk_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    timestamp = time.strftime("%Y%m%d%H%M%S")
    payload = {
        "BusinessShortCode": "174379",    
        "Password": "MTc0Mzc5YmZiMjc5ZjlhYTliZGJjZjE1OGU5N2RkNzFhNDY3Y2QyZTBjODkzMDU5YjEwZjc4ZTZiNzJhZGExZWQyYzkxOTIwMTYwMjE2MTY1NjI3",    
        "Timestamp": "20160216165627",    
        "TransactionType": "CustomerPayBillOnline",    
        "Amount": "1",    
        "PartyA": phone_number,    
        "PartyB": "174379",    
        "PhoneNumber": phone_number,    
        "CallBackURL": "https://fb43-105-163-157-64.ngrok-free.app/callback",    
        "AccountReference": "Test",    
        "TransactionDesc": "Test"
    }

    async with httpx.AsyncClient() as client:
        stk_response = await client.post(stk_url, json=payload, headers=headers)

    if stk_response.status_code != 200:
        error_detail = stk_response.json()
        print("STK Push failed:", error_detail)
        raise HTTPException(status_code=stk_response.status_code, detail="STK push failed")

    response_data = stk_response.json()
    checkout_request_id = response_data.get("CheckoutRequestID")
    
    if not checkout_request_id:
        raise HTTPException(status_code=500, detail="Missing CheckoutRequestID in response")

    # Wait and check payment status multiple times
    max_attempts = 6  # Will try 6 times over 60 seconds
    for attempt in range(max_attempts):
        await asyncio.sleep(10)  # Wait 10 seconds between checks
        
        query_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        timestamp = time.strftime("%Y%m%d%H%M%S")
        query_payload = {
            "BusinessShortCode": "174379",    
            "Password": "MTc0Mzc5YmZiMjc5ZjlhYTliZGJjZjE1OGU5N2RkNzFhNDY3Y2QyZTBjODkzMDU5YjEwZjc4ZTZiNzJhZGExZWQyYzkxOTIwMTYwMjE2MTY1NjI3",    
            "Timestamp": "20160216165627",
            "CheckoutRequestID": checkout_request_id
        }

        async with httpx.AsyncClient() as client:
            query_response = await client.post(query_url, json=query_payload, headers=headers)
        
        if query_response.status_code == 200:
            response_data = query_response.json()
            result_code = response_data.get("ResultCode")
            
            if result_code == "0":  # Successful payment
                # Generate user credentials
                username = f"user_{''.join(random.choices(string.digits, k=6))}"
                password = "pass123"
                if amount==1:
                    uptime='1h'
                elif amount==50:
                    uptime='1d'
                elif amount==150:
                    uptime='3d'
                elif amount==300:
                    uptime='1w'
                elif amount==1000:
                    uptime='4w'
                
                try:
                    api = connect_to_router()
                    hotspot_users = api.path("ip", "hotspot", "user")
                    hotspot_users.add(
                        name=username,
                        password=password,
                        profile="default",
                        **({"limit-uptime": uptime} if uptime else {})


                    )
                    return {
                        "status": "success",
                        "message": "Payment successful",
                        "credentials": {
                            "username": username,
                            "password": password
                        }
                    }
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to create hotspot user: {str(e)}")
            
            elif result_code != "1032":  # 1032 typically means "Request cancelled by user" or "pending"
                # If we get a definitive failure (not pending)
                raise HTTPException(status_code=400, detail="Payment failed or was cancelled")
        
        # If we're on the last attempt
        if attempt == max_attempts - 1:
            raise HTTPException(
                status_code=408, 
                detail="Payment timeout - please try again or check your M-PESA for any completed transaction"
            )
@app.get("/users")
def list_users():
    api = connect_to_router()
    users = api.path("user")
    return list(users)

@app.post("/users")
def create_user(user: User):
    api = connect_to_router()
    users = api.path("user")
    try:
        users.add(name=user.name, password=user.password, group=user.group)
        return {"message": "User created successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    api = connect_to_router()
    users = api.path("user")
    try:
        users.remove(user_id)
        return {"message": "User deleted successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")

@app.put("/users/{user_id}")
def modify_user(user_id: str, user: ModifyUser):
    api = connect_to_router()
    users = api.path("user")
    updates = {k: v for k, v in user.dict().items() if v is not None}
    try:
        users.set(id=user_id, **updates)
        return {"message": "User updated successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error updating user: {str(e)}")

@app.post("/vouchers")
def create_vouchers(voucher: VoucherRequest):
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")
    vouchers = []

    try:
        for _ in range(voucher.count):
            # Generate a unique username and password, you can use a library like `secrets` for this.
            username = f"voucher_{os.urandom(4).hex()}"
            password = os.urandom(4).hex()

            hotspot_users.add(
                name=username,
                password=password,
                profile=voucher.profile,
                **({"limit-uptime": voucher.duration} if voucher.duration else {})
            )

            vouchers.append({"username": username, "password": password})
            print(vouchers)

        return {"vouchers": vouchers}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error creating vouchers: {str(e)}")
        
@app.get("/hotspot-users")
def get_hotspot_users():
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")

    try:
        return {"users": list(hotspot_users)}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving users: {str(e)}")

@app.get("/hotspot-active-users")
def get_hotspot_active_users():
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot","active")

    try:
        return {"users": list(hotspot_users)}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving users: {str(e)}")


@app.post("/hotspot-users")
def add_hotspot_user(user: HotspotUserRequest):
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")

    try:
        hotspot_users.add(
            name=user.name,
            password=user.password,
            profile=user.profile,
            **({"limit-uptime": user.limit_uptime} if user.limit_uptime else {}),
           # address=user.address  # Optional field
        )
        return {"message": "Hotspot user created successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@app.post("/hotspot-users/{username}")
def delete_hotspot_user(username: str):
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")

    try:
        # Find the user by username
        users = list(hotspot_users)
        print(users)

        user = next((u for u in users if u['name'] == username), None)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        hotspot_users.remove(user['id'])
        return {"message": "Hotspot user deleted successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")



@app.post("/hotspot-users/{username}/kickout")
def kickout_hotspot_user(username: str):
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")
    hotspot_active = api.path("ip", "hotspot", "active")

    try:
        # Step 1: Find and disable the user
        users = list(hotspot_users)
        user = next((u for u in users if u['name'] == username), None)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Correct usage of update method
        hotspot_users.update(disabled="yes", **{".id": user[".id"]})

        # Step 2: Remove the user's active session (if they are active)
        active_sessions = list(hotspot_active)
        active_user = next((a for a in active_sessions if a['user'] == username), None)

        if active_user:
            hotspot_active.remove(active_user[".id"])

        return {
            "message": f"Hotspot user '{username}' has been disabled and logged out successfully"
        }
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error disabling or logging out user: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/hotspot/logout")
def logout_device(mac_address: str = None, ip_address: str = None):
    api = connect_to_router()
    hotspot_active = api.path("ip", "hotspot", "active")

    try:
        # Find the active session by MAC address or IP address
        sessions = list(hotspot_active)
        session = None

        if mac_address:
            session = next((s for s in sessions if s.get('mac-address') == mac_address), None)
        elif ip_address:
            session = next((s for s in sessions if s.get('address') == ip_address), None)

        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # Remove the session to log out the device
        hotspot_active.remove(session['.id'])
        return {"message": "Device logged out successfully"}

    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error logging out device: {str(e)}")


@app.get("/router-info")
def get_router_info():
    api = connect_to_router()

    try:
        # Fetch system identity (name)
        identity_query = api.path("system", "identity").select("name")
        identity = list(identity_query)[0]['name']
        
        # Fetch system resource info (CPU usage, uptime, etc.)
        resource_query = api.path("system", "resource").select(
            "uptime", 
            "version", 
            "cpu-load", 
            "cpu-frequency", 
            "cpu-count", 
            "free-memory", 
            "total-memory", 
            "free-hdd-space", 
            "total-hdd-space", 
            "architecture-name", 
            "board-name", 
            "platform"
        )
        resource = list(resource_query)[0]
        
        # Fetch system time and date
        clock_query = api.path("system", "clock").select("time", "date")
        clock = list(clock_query)[0]
        
        # Structure the response with desired information
        info = {
            "router_name": identity,
            "uptime": resource.get('uptime'),
            "version": resource.get('version'),
            "cpu_load": resource.get('cpu-load'),
            "cpu_frequency": resource.get('cpu-frequency'),
            "cpu_count": resource.get('cpu-count'),
            "free_memory": resource.get('free-memory'),
            "total_memory": resource.get('total-memory'),
            "free_hdd_space": resource.get('free-hdd-space'),
            "total_hdd_space": resource.get('total-hdd-space'),
            "architecture_name": resource.get('architecture-name'),
            "board_name": resource.get('board-name'),
            "platform": resource.get('platform'),
            "time": clock.get('time'),
            "date": clock.get('date'),
        }

        return info

    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving router info: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# To start the FastAPI server, run the command below:
# uvicorn main:app --reload
