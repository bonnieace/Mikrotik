from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException
#get all hotspot users service
def get_hotspot_users():
    db = SessionLocal()
    try:
        hotspot_users = crud.get_hotspot_users(db)
        hotspot_user_list = []
        for hotspot_user in hotspot_users:
            hotspot_user_list.append({
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
