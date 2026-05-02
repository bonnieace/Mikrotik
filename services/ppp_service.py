from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException
from services.mikrotik_service import connect_to_router

#create ppp user service
def create_ppp_user(name,email,pppoe_username,pppoe_password,mobile_number,location,apartment,profile: str, router_id: int):
    db = SessionLocal()
    try:
        # Provision the PPP secret on the MikroTik router first
        api = connect_to_router(router_id)
        ppp_secrets = api.path("ppp", "secret")
        ppp_secrets.add(
            name=pppoe_username,
            password=pppoe_password,
            profile=profile,
            service="pppoe",
        )

        ppp_user = crud.create_ppp_user(db, name, email, pppoe_username, pppoe_password, mobile_number, location, apartment, profile, router_id=router_id)
        crud.create_log(db, description=f"PPP User {name} created", phone_number=None)
        return {
            "name": ppp_user.name,
            "email": ppp_user.email,
            "pppoe_username": ppp_user.pppoe_username,
            "mobile_number": ppp_user.mobile_number,
            "location": ppp_user.location,
            "apartment": ppp_user.apartment,
            "profile": ppp_user.profile,
        }
    except Exception as e:
        crud.create_log(db, description=f"Failed to create PPP User {name}: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

#read all ppp users service
def get_ppp_users():
    db = SessionLocal()
    try:
        ppp_users = crud.get_ppp_users(db)
        ppp_user_list = []
        for ppp_user in ppp_users:
            ppp_user_list.append({
            "id":ppp_user.id,
            "name": ppp_user.name,
            "email": ppp_user.email,
            "pppoe_username": ppp_user.pppoe_username,
            "mobile_number": ppp_user.mobile_number,
            "location": ppp_user.location,
            "apartment": ppp_user.apartment,
            "profile": ppp_user.profile,
            "created_at":ppp_user.created_at,
            "expires_on":ppp_user.expires_on
                
            })
        return ppp_user_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get ppp users: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))