from fastapi import FastAPI, HTTPException
from librouteros import connect
from librouteros.exceptions import TrapError
from pydantic import BaseModel
from dotenv import load_dotenv
import os

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
            address=user.address  # Optional field
        )
        return {"message": "Hotspot user created successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@app.delete("/hotspot-users/{username}")
def delete_hotspot_user(username: str):
    api = connect_to_router()
    hotspot_users = api.path("ip", "hotspot", "user")

    try:
        # Find the user by username
        users = list(hotspot_users)
        user = next((u for u in users if u['name'] == username), None)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        hotspot_users.remove(user['id'])
        return {"message": "Hotspot user deleted successfully"}
    except TrapError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")
    

@app.delete("/hotspot/logout")
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
