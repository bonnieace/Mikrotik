import os
from k2connect import K2Connect

# Replace these with your actual KopoKopo sandbox credentials
BASE_URL = 'https://sandbox.kopokopo.com/'  # KopoKopo sandbox URL
CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_client_secret'

# Initialize the KopoKopo SDK
k2 = K2Connect(base_url=BASE_URL, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

def simulate_stk_push():
    try:
        # Step 1: Get an access token
        print("Requesting access token...")
        access_token = k2.token_service.get_access_token()
        print("Access token obtained successfully.")

        # Step 2: Initiate a payment request (STK Push)
        print("Initiating STK Push...")
        payment_request = k2.payment_request_service.create_payment_request(
            payment_channel='M-PESA',
            till_number='123456',  # Replace with your sandbox till number
            amount='1000',  # Amount in smallest currency unit (e.g., cents)
            currency='KES',
            metadata={
                'customer_id': '12345',
                'reference': 'Order #12345',
                'notes': 'Payment for order #12345'
            },
            callback_url='https://yourdomain.com/callback'  # Replace with your callback URL
        )

        # Step 3: Handle the response
        if payment_request['status'] == 'success':
            print('Payment request initiated successfully.')
            print('Resource location:', payment_request['location'])
        else:
            print('Failed to initiate payment request:', payment_request['errors'])

    except Exception as e:
        print("An error occurred:", str(e))

# Run the simulation
simulate_stk_push()
