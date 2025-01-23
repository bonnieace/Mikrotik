import os
import africastalking

# TODO: Initialize Africa's Talking

africastalking.initialize(
    username='sandbox',
    api_key='atsk_1156c81b10246f8a6f6f0bff36587d069ca629374a706db0b4ca5e2cfd29b86d76b2dc77'
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
        print (f'Houston, we have a problem: {e}')
sending()

    
