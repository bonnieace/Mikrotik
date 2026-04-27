import time
import base64

from fastapi import HTTPException
from database import crud
import httpx
import asyncio
import random
import string
from datetime import datetime, timedelta
from database.crud import create_hotspot_user, create_payment, create_log
from database.session import SessionLocal
from services.mikrotik_service import connect_to_router

# Constants
BASE_URL = "https://sandbox.safaricom.co.ke"
BUSINESS_SHORT_CODE = "174379"
LIPA_NA_MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"

def _generate_mpesa_password(timestamp: str) -> str:
    raw = BUSINESS_SHORT_CODE + LIPA_NA_MPESA_PASSKEY + timestamp
    return base64.b64encode(raw.encode()).decode()
CONSUMER_KEY = "YJwAugvyRWklll798WT0CRP60IlaC4GsmXaDaG3tESRzJzfF"
CONSUMER_SECRET = "ouz2P5YwOAKoRBnyJj8UVAIS8fZhqALYTM5NrUDG0Pu5Y5L8KdYw8z0TcFzdI0Nn"

async def initiate_stk_push(phone_number: str, amount: int):
    db = SessionLocal()
    api = connect_to_router()


    try:
        # Generate OAuth token
        auth_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
        if auth_response.status_code != 200:
            create_log(db, description=f"Failed to generate access token for {phone_number}", phone_number=phone_number)
            raise Exception("Failed to generate access token")
        
        access_token = auth_response.json().get("access_token")
        if not access_token:
            create_log(db, description=f"Access token missing for {phone_number}", phone_number=phone_number)
            raise Exception("Access token missing in response")
        
        # Initiate STK Push
        stk_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        timestamp = time.strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": BUSINESS_SHORT_CODE,
            "Password": _generate_mpesa_password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",    
            "Amount": amount,    
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
            create_log(db, description=f"STK Push failed for {phone_number}: {error_detail}", phone_number=phone_number)
            raise Exception("STK push failed")

        response_data = stk_response.json()
        checkout_request_id = response_data.get("CheckoutRequestID")
        if not checkout_request_id:
            create_log(db, description=f"Missing CheckoutRequestID for {phone_number}", phone_number=phone_number)
            raise Exception("Missing CheckoutRequestID in response")

        # Wait and check payment status multiple times
        max_attempts = 6  # Will try 6 times over 60 seconds
        for attempt in range(max_attempts):
            await asyncio.sleep(10)  # Wait 10 seconds between checks
            
            query_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            query_timestamp = time.strftime("%Y%m%d%H%M%S")
            query_payload = {
                "BusinessShortCode": BUSINESS_SHORT_CODE,
                "Password": _generate_mpesa_password(query_timestamp),
                "Timestamp": query_timestamp,
                "CheckoutRequestID": checkout_request_id
            }

            async with httpx.AsyncClient() as client:
                query_response = await client.post(query_url, json=query_payload, headers=headers)
            
            if query_response.status_code == 200:
                response_data = query_response.json()
                result_code = response_data.get("ResultCode")
                
                if result_code == "0":  # Successful payment
                    # Generate user credentials
                    username = ''.join(random.choices(string.digits, k=8))
                    password = "pass123"
                    if amount == 10:
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

                    #add user to mikrotik use try catch with logging
                    try:
                        
                        hotspot_users = api.path("ip", "hotspot", "user")
                        hotspot_users.add(
                            name=username,
                            password=password,
                            profile="default",
                            **({"limit-uptime": uptime} if uptime else {})

                        )
                    except Exception as e:
                        create_log(db, description=f"Failed to add hotspot user {username} to MikroTik: {str(e)}", phone_number=phone_number)
                        raise HTTPException(status_code=400, detail=str(e))
                    
                    
                    
                    
                    # Create hotspot user
                    hotspot_user = create_hotspot_user(db, phone_number=phone_number, amount=amount,otp=username)
                    # Log payment
                    create_payment(db, invoice=checkout_request_id, amount=amount, user_type="hotspot", user_id=hotspot_user.id)
                    # Log success
                    create_log(db, description=f"Payment successful for user {username}", phone_number=phone_number)

                    return {
                        "status": "success",
                        "message": "Payment successful",
                        "credentials": {
                            "username": username,
                            "password": password
                        }
                    }
                
                elif result_code != "1032":  # 1032 typically means "Request cancelled by user" or "pending"
                    create_log(db, description=f"Payment failed for {phone_number}: {response_data.get('ResultDesc')}", phone_number=phone_number)
                    raise Exception("Payment failed or was cancelled")
            
            # If we're on the last attempt
            if attempt == max_attempts - 1:
                create_log(db, description=f"Payment timeout for {phone_number}", phone_number=phone_number)
                raise Exception("Payment timeout - please try again or check your M-PESA for any completed transaction")
    finally:
        db.close()

#read all payments service
def get_payments():
    db = SessionLocal()
    try:
        payments = crud.get_payments(db)
        payment_list = []
        for payment in payments:
            payment_list.append({
                "id":payment.id,
                "invoice": payment.invoice,
                "amount": payment.amount,
                "user_type": payment.user_type,
                "user_id": payment.user_id,
                "created_at":payment.created_at
            })
        return payment_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get payments: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))
    
#read payments by user type service
def get_payments_by_user_type(user_type: str):
    db = SessionLocal()
    try:
        payments = crud.get_payments_by_user_type(db, user_type)
        payment_list = []
        for payment in payments:
            payment_list.append({
                "id":payment.id,
                "invoice": payment.invoice,
                "amount": payment.amount,
                "user_type": payment.user_type,
                "user_id": payment.user_id,
                "created_at":payment.created_at

            })
        return payment_list
    except Exception as e:
        crud.create_log(db, description=f"Failed to get payments: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))
    
#return total payment for by user type
def get_total_payment_by_user_type(user_type: str):
    db = SessionLocal()
    try:
        payments = crud.get_payments_by_user_type(db, user_type)
        total_payment = 0
        for payment in payments:
            total_payment += payment.amount
        return total_payment
    except Exception as e:
        crud.create_log(db, description=f"Failed to get payments: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))
#read payment totals for the current day by user type
def get_total_payment_for_today_by_user_type(user_type: str):
    db = SessionLocal()
    try:
    
        payments = crud.get_payment_totals_for_today_by_user_type(db, user_type )
        
        return payments
    except Exception as e:
        crud.create_log(db, description=f"Failed to get today's payments: {str(e)}", phone_number=None)
        raise HTTPException(status_code=400, detail=str(e))
