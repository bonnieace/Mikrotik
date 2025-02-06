import os
import k2connect # type: ignore

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Replace these with your actual KopoKopo sandbox credentials
BASE_URL = 'https://sandbox.kopokopo.com'#os.getenv("BASE_URL")# KopoKopo sandbox URL
CLIENT_ID = '7rrG_KKqLQp4NJpKnd0qj6yKA8D8M94ScIuFhG9yviY'# Your KopoKopo sandbox client ID
CLIENT_SECRET = 'dti9Dsra5xlr3psXFOeg7o0biFMSWkHsjMdYluRnFc4'# Your KopoKopo sandbox client secret



def simulate_stk_push():
    try:
        #authenticate
        
        k2connect.initialize(CLIENT_ID, CLIENT_SECRET, "https://sandbox.kopokopo.com/oauth/token")
        token_service = k2connect.Tokens
        access_token_request = token_service.request_access_token()
        access_token = token_service.get_access_token(access_token_request)
        print(access_token)
        # Step 2: Initiate a payment request (STK Push)
        request_body ={
        "access_token": access_token,
        "callback_url": "https://webhook.site/52fd1913-778e-4ee1-bdc4-74517abb758d",
        "first_name": "Boniface",
        "last_name": "masota",
        "email": "bonniemasota@gmail.com",
        "payment_channel": "MPESA",
        "phone_number": "+254722218106",
        "till_number": "K000000",
        "amount": "10"
        }
        print("Initiating STK Push...")
        stk_service = k2connect.ReceivePayments
        stk_push_location = stk_service.create_payment_request(request_body)
        print(stk_push_location)

        # Step 3: Handle the response
        result_handler = k2connect.ResultHandler
        processed_payload = result_handler.process(request)
        decomposed_result = payload_decomposer.decompose(processed_payload)
        # Processed stk result in json format
        print(decomposed_result)
    except Exception as e:
        print("An error occurred:", str(e))

# Run the simulation
simulate_stk_push()
