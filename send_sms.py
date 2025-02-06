import os
import africastalking
from dotenv import load_dotenv
import os

# TODO: Initialize Africa's Talking
load_dotenv()
africastalking.initialize(
    username=os.getenv('AFRICASTALKING_USERNAME'),
    api_key=os.getenv('AFRICASTALKING_API_KEY')
)

sms = africastalking.SMS




#TODO: Send message
def sending():
    # Set the numbers in international format
    recipients = ["+254722218106"]
    # Set your message
    message = "Your Uzanet hotspot subscripiton has been depleted please use this link to renew : http:/uzanet.com/renew!"
    # Set your shortCode or senderId
    sender = "18856"
    try:
        response = sms.send(message, recipients, sender)
        print (response)
    except Exception as e:
        print (f' we have a problem: {e}')
sending()

    
