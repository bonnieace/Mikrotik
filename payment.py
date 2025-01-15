from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/callback', methods=['POST'])
def mpesa_callback():
    """
    Handle the M-Pesa callback from Safaricom.
    """
    try:
        callback_data = request.json  # Get the JSON payload
        print("Callback received:", callback_data)
        
        # Process the callback data as needed
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})  # Acknowledge receipt
    except Exception as e:
        print("Error processing callback:", e)
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"})

if __name__ == "__main__":
    app.run(port=5000)
