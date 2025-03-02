from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException
from services.mikrotik_service import connect_to_router
import httpx
#get all hotspot users service
def get_hotspot_users():
    db = SessionLocal()
    try:
        hotspot_users = crud.get_hotspot_users(db)
        hotspot_user_list = []
        for hotspot_user in hotspot_users:
            hotspot_user_list.append({
                "id":hotspot_user.id,
                "phone_number": hotspot_user.phone_number,
                "amount": hotspot_user.amount,
                "otp": hotspot_user.otp,
                "expires_at": hotspot_user.expires_at,
                "created_at": hotspot_user.created_at
            })
        return hotspot_user_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get hotspot users: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))

#create hotspot user
def create_hotspot_user(phone_number: str, amount: int, otp: str):
    db = SessionLocal()
    api=connect_to_router()
    try:
        if amount == 1:
            uptime = '1h'
        elif amount == 50:
            uptime = '1d'
        elif amount == 150:
            uptime = '3d'
        elif amount == 300:
            uptime = '1w'
        elif amount == 1000:
            uptime = '4w'
        else:
            uptime = None
        
        #create hotspot user 
        hotspot_users = api.path("ip", "hotspot", "user")
        hotspot_users.add(
            name=otp,
            password="pass123",
            profile="default",
            **({"limit-uptime": uptime} if uptime else {})

        )
        hotspot_user=crud.create_hotspot_user(db,phone_number=phone_number,amount=amount,otp=otp)
        crud.create_log(db, description=f"Hotspot User {phone_number} created", phone_number=phone_number)
        #return user details
        return {
            "phone_number": hotspot_user.phone_number,
            "amount": hotspot_user.amount,
            "otp": hotspot_user.otp,
            "expires_at": hotspot_user.expires_at,
            "created_at": hotspot_user.created_at
        }
    except Exception as e:
        crud.create_log(db, description=f"Failed to create hotspot user: {str(e)}", phone_number=phone_number)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

