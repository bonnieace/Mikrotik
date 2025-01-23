# Radius Server Codebase for MikroTik Integration

This document provides an overview of the structure and functionality of the Radius server codebase built for MikroTik integration. The backend uses FastAPI with Uvicorn, and the frontend includes a captive portal.

---

## Project Structure

```
mikrotik/
|-- hotspot/                      # Contains hotspot submodule and related files
|   |-- hotspot/                  # Code from a MikroTik router
|   |-- redirect/                 # Folder for redirection HTML
|       |-- redirect.html         # Redirect page
|   |-- login                     # Captive portal login file
|-- .env                          # Environment variables
|-- main.py                       # Entry point for the FastAPI application
|-- requirements.txt              # Python dependencies
|-- mpesa.py                      # Integration with Mpesa for payments
|-- send_sms.py                   # SMS functionality
|-- kopokopo.py                   # Integration with Kopokopo for payment services
```

---

## Environment Variables

The `.env` file contains configuration settings required for connecting to the MikroTik router. These variables should be set before running the application:

```
MIKROTIK_HOST=<router-ip>
MIKROTIK_PORT=<api-port>
MIKROTIK_USER=<username>
MIKROTIK_PASSWORD=<password>
```

---

## Key Components

### 1. **`main.py`**
The entry point of the FastAPI application:
- Initializes the server using Uvicorn.
- Defines routes and middleware.
- Handles interactions between the frontend and backend.

### 2. **`hotspot` Submodule**
Contains MikroTik-specific hotspot configurations and captive portal logic:
- Manages user authentication and session handling via the MikroTik router.
- Includes a `redirect.html` file for handling user redirection.
- `login` file serves as the captive portal for user login.

### 3. **Payment Integration Files**
- **`mpesa.py`**: Handles Mpesa payment transactions.
- **`send_sms.py`**: Sends SMS notifications, e.g., for payment confirmations or account updates.
- **`kopokopo.py`**: Manages payment services through Kopokopo, an alternative payment gateway.

### 4. **`requirements.txt`**
Lists all the Python dependencies required for the project. Install them using:
```bash
pip install -r requirements.txt
```

---

## Setting Up and Running the Application

1. **Set Environment Variables**
   Ensure the `.env` file contains the correct MikroTik router details:
   ```
   MIKROTIK_HOST=192.168.88.1
   MIKROTIK_PORT=8728
   MIKROTIK_USER=admin
   MIKROTIK_PASSWORD=your_password
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Access the Captive Portal**
   Navigate to `http://<server-ip>:8000/` in your browser to view the captive portal.

---

## Future Enhancements
1. Add a dashboard for monitoring user activity and payments.
2. Improve the captive portal UI for better user experience.
3. Integrate additional payment gateways.
4. Implement logging and analytics for system performance.
5. Add HTTPS support for secure communication.
