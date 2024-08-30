from fastapi import FastAPI, HTTPException
from routeros_api import RouterOsApi
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import secrets

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
    address: str = None  # Optional, depending on your requirements


# Utility function to connect to the router
def connect_to_router():
    try:
        api = RouterOsApi(host=MIKROTIK_HOST, username=MIKROTIK_USER, password=MIKROTIK_PASSWORD, port=MIKROTIK_PORT)
        return api
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

# Endpoints
@app.get("/users")
def list_users():
    api = connect_to_router()
    try:
        users = api.get_resource('user').get()
        return users
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving users: {str(e)}")

@app.post("/users")
def create_user(user: User):
    api = connect_to_router()
    try:
        api.get_resource('user').create(name=user.name, password=user.password, group=user.group)
        return {"message": "User created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    api = connect_to_router()
    try:
        api.get_resource('user').delete(id=user_id)
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")

@app.put("/users/{user_id}")
def modify_user(user_id: str, user: ModifyUser):
    api = connect_to_router()
    updates = {k: v for k, v in user.dict().items() if v is not None}
    try:
        api.get_resource('user').update(id=user_id, **updates)
        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating user: {str(e)}")

@app.post("/vouchers")
def create_vouchers(voucher: VoucherRequest):
    api = connect_to_router()
    vouchers = []
    try:
        for _ in range(voucher.count):
            # Generate a unique username and password
            username = f"voucher_{secrets.token_hex(4)}"
            password = secrets.token_hex(4)

            api.get_resource('ip/hotspot/user').create(
                name=username,
                password=password,
                profile=voucher.profile,
                limit_uptime=voucher.duration
            )
            vouchers.append({"username": username, "password": password})

        return {"vouchers": vouchers}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating vouchers: {str(e)}")

@app.get("/hotspot-users")
def get_hotspot_users():
    api = connect_to_router()
    try:
        users = api.get_resource('ip/hotspot/user').get()
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving users: {str(e)}")

@app.post("/hotspot-users")
def add_hotspot_user(user: HotspotUserRequest):
    api = connect_to_router()
    try:
        api.get_resource('ip/hotspot/user').create(
            name=user.name,
            password=user.password,
            profile=user.profile,
            limit_uptime=user.limit_uptime,
            address=user.address
        )
        return {"message": "Hotspot user created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@app.delete("/hotspot-users/{username}")
def delete_hotspot_user(username: str):
    api = connect_to_router()
    try:
        users = api.get_resource('ip/hotspot/user').get()
        user = next((u for u in users if u['name'] == username), None)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        api.get_resource('ip/hotspot/user').delete(id=user['id'])
        return {"message": "Hotspot user deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")

# To start the FastAPI server, run the command below:
# uvicorn main:app --reload
