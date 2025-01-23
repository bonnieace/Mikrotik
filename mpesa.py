from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


import httpx
import time

app = FastAPI()
# Mount the hotspot directory to serve static files

app.mount("/hotspot", StaticFiles(directory="hotspot"), name="hotspot")
origins = [
    "*",  # Replace with the origin of your frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

# Safaricom API credentials
BASE_URL = "https://sandbox.safaricom.co.ke"
CONSUMER_KEY = "YJwAugvyRWklll798WT0CRP60IlaC4GsmXaDaG3tESRzJzfF"
CONSUMER_SECRET = "ouz2P5YwOAKoRBnyJj8UVAIS8fZhqALYTM5NrUDG0Pu5Y5L8KdYw8z0TcFzdI0Nn"
@app.post("/callback")
async def mpesa_callback(data: dict):
    callback_body = data.get("Body", {}).get("stkCallback", {})
    result_code = callback_body.get("ResultCode")
    result_desc = callback_body.get("ResultDesc")
    metadata = callback_body.get("CallbackMetadata", {}).get("Item", [])
    
    if result_code == 0:
        print("Payment successful:", metadata)
        # Store or process the payment details here
    else:
        print("Payment failed:", result_desc)
    
    return {"status": "processed"}

@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

@app.get("/hotspot/redirect")
async def serve_redirect_html():
    """
    Serve the HTML file located at hotspot/redirect/index.html.
    """
    file_path = "hotspot/redirect/login.html"
    return FileResponse(file_path)

@app.post("/stkpush/initiate")
async def initiate_stk_push(phone_number: str, amount: int):
    # Generate OAuth token
    auth_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    async with httpx.AsyncClient() as client:
        auth_response = await client.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    if auth_response.status_code != 200:
        raise HTTPException(status_code=auth_response.status_code, detail="Failed to generate access token")
    
    access_token = auth_response.json().get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token missing in response")
    
    # Initiate STK Push
    stk_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    timestamp = time.strftime("%Y%m%d%H%M%S")
    payload = {
        "BusinessShortCode": "174379",    
        "Password": "MTc0Mzc5YmZiMjc5ZjlhYTliZGJjZjE1OGU5N2RkNzFhNDY3Y2QyZTBjODkzMDU5YjEwZjc4ZTZiNzJhZGExZWQyYzkxOTIwMTYwMjE2MTY1NjI3",    
        "Timestamp": "20160216165627",    
        "TransactionType": "CustomerPayBillOnline",    
        "Amount": str(amount),    
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
        print("STK Push failed:", error_detail)
        raise HTTPException(status_code=stk_response.status_code, detail="STK push failed")

    response_data = stk_response.json()
    checkout_request_id = response_data.get("CheckoutRequestID")
    
    if not checkout_request_id:
        raise HTTPException(status_code=500, detail="Missing CheckoutRequestID in response")

    # Wait and check payment status multiple times
    max_attempts = 6  # Will try 6 times over 60 seconds
    for attempt in range(max_attempts):
        await asyncio.sleep(10)  # Wait 10 seconds between checks
        
        query_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        timestamp = time.strftime("%Y%m%d%H%M%S")
        query_payload = {
            "BusinessShortCode": "174379",    
            "Password": "MTc0Mzc5YmZiMjc5ZjlhYTliZGJjZjE1OGU5N2RkNzFhNDY3Y2QyZTBjODkzMDU5YjEwZjc4ZTZiNzJhZGExZWQyYzkxOTIwMTYwMjE2MTY1NjI3",    
            "Timestamp": "20160216165627",
            "CheckoutRequestID": checkout_request_id
        }

        async with httpx.AsyncClient() as client:
            query_response = await client.post(query_url, json=query_payload, headers=headers)
        
        if query_response.status_code == 200:
            response_data = query_response.json()
            result_code = response_data.get("ResultCode")
            
            if result_code == "0":  # Successful payment
                print("Payment successful:", response_data)
                return {"status": "success", "data": response_data}