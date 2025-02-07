from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException
#create ppp user service
def create_ppp_user(name: str):
    db = SessionLocal()
    try:
        ppp_user = crud.create_ppp_user(db, name)
        crud.create_log(db, description=f"PPP User {name} created", phone_number=None)
        return {
            "name": ppp_user.name
        }
    except Exception as e:
        crud.create_log(db, description=f"Failed to create PPP User {name}: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))

#read all ppp users service
def get_ppp_users():
    db = SessionLocal()
    try:
        ppp_users = crud.get_ppp_users(db)
        ppp_user_list = []
        for ppp_user in ppp_users:
            ppp_user_list.append({
                "name": ppp_user.name
            })
        return ppp_user_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get ppp users: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))