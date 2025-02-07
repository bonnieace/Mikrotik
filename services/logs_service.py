from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException
#log service
def create_log(description: str, phone_number: str = None):
    db = SessionLocal()
    try:
        log = crud.create_log(db, description, phone_number)
        return log
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#read all logs service
def get_logs():
    db = SessionLocal()
    try:
        logs = crud.get_logs(db)
        log_list = []
        for log in logs:
            log_list.append({
                "description": log.description,
                "phone_number": log.phone_number
            })
        return log_list
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


