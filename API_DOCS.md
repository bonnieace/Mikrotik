# Uzanet MikroTik API — Endpoint Reference

Base URL (local dev): `http://localhost:8000`

The application exposes two FastAPI apps:
- **`main.py`** — Primary app (router management + hotspot + M-PESA payments)
- **`ppp.py`** — PPP/PPPoE client management app

---

## Table of Contents

1. [General](#general)
2. [Router Users (RouterOS)](#router-users-routeros)
3. [Hotspot Users](#hotspot-users)
4. [Vouchers](#vouchers)
5. [Payments — M-PESA STK Push](#payments--m-pesa-stk-push)
6. [PPP / PPPoE Clients](#ppp--pppoe-clients)
7. [PPP Profiles](#ppp-profiles)
8. [Static Files](#static-files)

---

## General

### `GET /`
**Description:** Health check / welcome message.

**Response `200`**
```json
{ "message": "Welcome to the API" }
```

---

### `GET /router-info`
**Description:** Returns live system information from the MikroTik router.

**Response `200`**
```json
{
  "router_name": "MikroTik",
  "uptime": "5d2h34m",
  "version": "7.16",
  "cpu_load": "4",
  "cpu_frequency": "600",
  "cpu_count": "1",
  "free_memory": "52428800",
  "total_memory": "67108864",
  "free_hdd_space": "1048576",
  "total_hdd_space": "16777216",
  "architecture_name": "mipsbe",
  "board_name": "RB951Ui-2HnD",
  "platform": "MikroTik",
  "time": "12:34:56",
  "date": "apr/26/2026"
}
```

---

## Router Users (RouterOS)

These endpoints manage login accounts on the MikroTik router itself (not hotspot users).

### `GET /users`
**Description:** List all RouterOS user accounts.

**Response `200`** — Array of user objects from the router.

---

### `POST /users`
**Description:** Create a new RouterOS user account.

**Request Body**
```json
{
  "name": "admin2",
  "password": "securepass",
  "group": "read"
}
```
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | ✅ | — | Username |
| `password` | string | ✅ | — | Password |
| `group` | string | ❌ | `"read"` | RouterOS group (`read`, `write`, `full`) |

**Response `200`**
```json
{ "message": "User created successfully" }
```

---

### `PUT /users/{user_id}`
**Description:** Modify an existing RouterOS user (password, group, or disabled state).

**Path Parameter:** `user_id` — RouterOS internal ID (e.g., `*1`)

**Request Body** (all fields optional)
```json
{
  "password": "newpassword",
  "group": "full",
  "disabled": false
}
```

**Response `200`**
```json
{ "message": "User updated successfully" }
```

---

### `DELETE /users/{user_id}`
**Description:** Delete a RouterOS user account.

**Path Parameter:** `user_id` — RouterOS internal ID

**Response `200`**
```json
{ "message": "User deleted successfully" }
```

---

## Hotspot Users

### `GET /hotspot-users`
**Description:** List all configured hotspot users.

**Response `200`**
```json
{
  "users": [
    {
      "name": "user_123456",
      "profile": "default",
      "limit-uptime": "1d",
      ...
    }
  ]
}
```

---

### `GET /hotspot-active-users`
**Description:** List currently active/connected hotspot sessions.

**Response `200`**
```json
{
  "users": [
    {
      "user": "user_123456",
      "address": "192.168.88.10",
      "mac-address": "AA:BB:CC:DD:EE:FF",
      "uptime": "00:15:32",
      ...
    }
  ]
}
```

---

### `POST /hotspot-users`
**Description:** Manually create a hotspot user.

**Request Body**
```json
{
  "name": "john_doe",
  "password": "pass123",
  "profile": "default",
  "limit_uptime": "1d"
}
```
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Username |
| `password` | string | ✅ | Password |
| `profile` | string | ✅ | Hotspot profile name |
| `limit_uptime` | string | ✅ | Duration limit (e.g., `"1h"`, `"1d"`, `"1w"`) |

**Response `200`**
```json
{ "message": "Hotspot user created successfully" }
```

---

### `POST /hotspot-users/{username}`
**Description:** Delete a hotspot user by username.

> ⚠️ Note: Uses `POST` method for deletion — consider using `DELETE` in a future revision.

**Path Parameter:** `username` — The hotspot username

**Response `200`**
```json
{ "message": "Hotspot user deleted successfully" }
```

**Response `404`** — User not found.

---

### `POST /hotspot-users/{username}/kickout`
**Description:** Disable a hotspot user and forcibly terminate their active session.

**Path Parameter:** `username` — The hotspot username

**Response `200`**
```json
{
  "message": "Hotspot user 'john_doe' has been disabled and logged out successfully"
}
```

---

### `POST /hotspot/logout`
**Description:** Log out a connected device by MAC address or IP address.

**Query Parameters** (at least one required)
| Parameter | Type | Description |
|-----------|------|-------------|
| `mac_address` | string | Device MAC address (e.g., `AA:BB:CC:DD:EE:FF`) |
| `ip_address` | string | Device IP address (e.g., `192.168.88.10`) |

**Response `200`**
```json
{ "message": "Device logged out successfully" }
```

**Response `404`** — No matching active session found.

---

## Vouchers

### `POST /vouchers`
**Description:** Bulk-generate hotspot voucher credentials and add them to the router.

**Request Body**
```json
{
  "profile": "default",
  "count": 5,
  "duration": "1d"
}
```
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `profile` | string | ✅ | — | Hotspot profile to assign |
| `count` | integer | ❌ | `1` | Number of vouchers to generate |
| `duration` | string | ✅ | — | Uptime limit (e.g., `"1h"`, `"1d"`, `"1w"`) |

**Response `200`**
```json
{
  "vouchers": [
    { "username": "voucher_a1b2c3d4", "password": "e5f6a7b8" },
    { "username": "voucher_c9d0e1f2", "password": "a3b4c5d6" }
  ]
}
```

---

## Payments — M-PESA STK Push

### `POST /stkpush/initiate`
**Description:** Initiate a Safaricom M-PESA STK Push payment. Upon successful payment confirmation, automatically creates a hotspot user with an uptime limit mapped to the paid amount.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `phone_number` | string | ✅ | Customer phone number (e.g., `254722000000`) |
| `amount` | integer | ✅ | Amount in KES |

**Amount → Uptime Mapping**
| Amount (KES) | Hotspot Duration |
|-------------|-----------------|
| 1 | 1 hour |
| 50 | 1 day |
| 150 | 3 days |
| 300 | 1 week |
| 1000 | 4 weeks |

**Response `200`** (payment confirmed + user created)
```json
{
  "status": "success",
  "message": "Payment successful",
  "credentials": {
    "username": "user_483920",
    "password": "pass123"
  }
}
```

**Response `400`** — Payment failed or cancelled.  
**Response `408`** — Payment timed out (no confirmation within ~60 seconds).

---

### `POST /callback`
**Description:** Webhook endpoint called by Safaricom after an STK Push transaction completes. Receives and logs the payment result.

**Request Body** (sent by Safaricom)
```json
{
  "Body": {
    "stkCallback": {
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [...]
      }
    }
  }
}
```

**Response `200`**
```json
{ "status": "processed" }
```

---

## PPP / PPPoE Clients

> Defined in `ppp.py`. Run as a separate FastAPI instance.

### `POST /ppp/add`
**Description:** Add a new PPP/PPPoE secret (client credentials) to the router.

**Request Body**
```json
{
  "username": "client01",
  "password": "secret123",
  "profile": "default",
  "service": "pppoe"
}
```
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `username` | string | ✅ | — | PPP username |
| `password` | string | ✅ | — | PPP password |
| `profile` | string | ❌ | `"default"` | PPP profile to assign |
| `service` | string | ❌ | `"pppoe"` | Service type (`pppoe`, `pptp`, `l2tp`, etc.) |

**Response `200`**
```json
{ "message": "PPP client 'client01' added successfully" }
```

---

### `GET /ppp/clients`
**Description:** List all PPP secrets (configured clients).

**Response `200`**
```json
{
  "clients": [
    {
      "username": "client01",
      "profile": "default",
      "service": "pppoe"
    }
  ]
}
```

---

### `GET /ppp/clients/active`
**Description:** List currently active PPP connections.

**Response `200`**
```json
{
  "clients": [
    {
      "username": "client01",
      "profile": "default",
      "service": "pppoe"
    }
  ]
}
```

---

### `POST /ppp/clients/login`
**Description:** Validate PPP client credentials (username + password check against router secrets).

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | PPP username |
| `password` | string | ✅ | PPP password |

**Response `200`**
```json
{ "message": "PPP client 'client01' successfully logged in." }
```

**Response `404`** — Client not found.  
**Response `401`** — Invalid credentials.

---

### `POST /ppp/renew`
**Description:** Renew a PPP client's uptime limit after verifying an M-PESA payment via STK Push query.

**Request Body**
```json
{
  "username": "client01",
  "amount": 300
}
```
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | ✅ | PPP client username |
| `amount` | integer | ✅ | Payment amount in KES |

**Amount → Uptime Mapping**
| Amount (KES) | Duration |
|-------------|---------|
| 10 | 1 hour |
| 50 | 1 day |
| 150 | 3 days |
| 300 | 1 week |
| 1000 | 4 weeks |

**Response `200`**
```json
{ "message": "PPP client 'client01' renewed successfully" }
```

**Response `400`** — Invalid amount or payment failed.  
**Response `404`** — PPP client not found.

---

## PPP Profiles

### `GET /ppp/profiles`
**Description:** List all PPP profiles configured on the router.

**Response `200`**
```json
{
  "profiles": [
    {
      "name": "default",
      "rate_limit": "10M/10M",
      "local_address": "192.168.1.1",
      "remote_address": "192.168.1.0/24"
    }
  ]
}
```

---

### `POST /ppp/profiles`
**Description:** Add a new PPP profile to the router.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | Profile name |
| `rate_limit` | string | ❌ | Bandwidth limit (e.g., `"10M/10M"`) |
| `local_address` | string | ❌ | Local IP address |
| `remote_address` | string | ❌ | Remote address pool or IP |

**Response `200`**
```json
{ "message": "PPP profile 'premium' successfully added." }
```

---

## Static Files

| Path | Source Directory | Description |
|------|-----------------|-------------|
| `GET /hotspot/*` | `hotspot/` | Serves all MikroTik hotspot portal HTML, CSS, JS, and assets |
| `GET /hotspot/redirect` | `hotspot/redirect/login.html` | Serves the redirect login page |

---

## Error Responses

All endpoints use standard HTTP status codes:

| Code | Meaning |
|------|---------|
| `400` | Bad request / MikroTik API error |
| `401` | Invalid credentials |
| `404` | Resource not found |
| `408` | Request timeout (payment polling) |
| `500` | Unexpected server or connection error |

Error response shape:
```json
{ "detail": "Error message describing what went wrong" }
```
