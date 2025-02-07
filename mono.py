from fastapi import FastAPI, HTTPException
from services.hotspot_service import get_hotspot_users
from services.logs_service import create_log, get_logs
from services.payment_service import get_payments, get_payments_by_user_type, get_total_payment_by_user_type, initiate_stk_push
from services.package_service import create_package, get_packages
from services.ppp_service import create_ppp_user, get_ppp_users

app = FastAPI()

@app.post("/stkpush/initiate")
async def initiate_stk_push_endpoint(phone_number: str, amount: int):
    try:
        result = await initiate_stk_push(phone_number, amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

#create package endpoint
@app.post("/package")
async def create_package_endpoint(name: str, description: str, price: float, service_type: str, validity_days: int):
    try:
        package = create_package(name, description, price, service_type, validity_days)
        return package
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#read all packages endpoint
@app.get("/packages")
async def get_packages_endpoint():
    try:
        packages = get_packages()
        return packages
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

#read all payments endpoint
@app.get("/payments")
async def get_payments_endpoint():
    try:
        payments = get_payments()
        return payments
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#read payments by user type endpoint
@app.get("/payments/{user_type}")
async def get_payments_by_user_type_endpoint(user_type: str):
    try:
        payments = get_payments_by_user_type(user_type)
        return payments
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#return total payment for a specific  usertype 
@app.get("/payments/total/{user_type}")
async def get_total_payment_by_user_type_endpoint(user_type: str):
    try:
        total_payment = get_total_payment_by_user_type(user_type)
        return {"total_payment": total_payment}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 

#get hotspot users endpoint
@app.get("/hotspot_users")
async def get_hotspot_users_endpoint():
    try:
        hotspot_users = get_hotspot_users()
        return hotspot_users
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#get logs endpoint
@app.get("/logs")
async def get_logs_endpoint():
    try:
        logs = get_logs()
        return logs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
# #create log endpoint
@app.post("/log")
async def create_log_endpoint(description: str, phone_number: str = None):
    try:
        log = create_log(description, phone_number)
        return log
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
 #create ppp user endpoint
@app.post("/ppp_user")
async def create_ppp_user_endpoint(name: str):
    try:
        ppp_user = create_ppp_user(name)
        return ppp_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
#read all ppp users endpoint
@app.get("/ppp_users")
async def get_ppp_users_endpoint():
    try:
        ppp_users = get_ppp_users()
        return ppp_users
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))