from database import crud
from database import models
from database.session import SessionLocal
from datetime import datetime
from typing import List
from fastapi import HTTPException

#create package service
#do logs as well
def create_package(name: str, description: str, price: float, service_type: str, validity_days: int, router_id: int = None):
    db = SessionLocal()
    try:
        package = crud.create_package(db, name, description, price, service_type, validity_days, router_id=router_id)
        crud.create_log(db, description=f"Package {name} created", phone_number=None, router_id=router_id)
        #return package info instead of package object
        return {
            "name": package.name,
            "description": package.description,
            "price": package.price,
            "service_type": package.service_type,
            "validity_days": package.validity_days
        }

        
    except Exception as e:
        crud.create_log(db, description=f"Failed to create package {name}: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))

#read all packages service

def get_packages(router_id: int = None):
    db = SessionLocal()
    try:
        packages = crud.get_packages(db, router_id=router_id)
        package_list = []
        for package in packages:
            package_list.append({
                "id" : package.id,
                "name": package.name,
                "description": package.description,
                "price": package.price,
                "service_type": package.service_type,
                "validity_days": package.validity_days,
                "router_id": package.router_id
            })
        return package_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get packages: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))