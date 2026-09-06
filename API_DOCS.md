# Uzanet API v1

Base path: `/api/v1`. JSON is used unless the endpoint is the OAuth2-compatible token form. Error responses use `{"detail": "..."}` and may include `request_id`; the same ID is returned in `X-Request-ID`.

## Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/token` | Form fields `username`, `password`; returns bearer token and expiry. |
| GET | `/me` | Current operator profile. |
| POST | `/auth/logout` | Revokes all tokens at the current token version. |
| POST | `/users/change-password` | Changes password and revokes existing tokens. |
| GET/POST | `/users` | Superadmin operator management. |

All remaining admin endpoints require `Authorization: Bearer <token>`.

## Routers and onboarding

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/routers` | List owned routers or add a direct-control router. |
| PATCH/DELETE | `/routers/{router_uid}` | Update or remove an owned router. |
| GET | `/routers/status` | Authenticated status for all visible routers. |
| GET | `/routers/{router_uid}/status` | Authenticated status for one router. |
| POST | `/routers/onboarding` | Generate a one-time legacy-compatible L2TP `.rsc` bundle. |
| POST | `/router-onboarding/claim` | One-time RouterOS claim callback; no operator token. |
| GET | `/routers/{router_uid}/active-users` | Current Hotspot and PPPoE sessions. |
| GET | `/routers/{router_uid}/traffic` | Current bridge RX/TX rate. |

Start onboarding:

```json
{
  "name": "Town branch",
  "portal_slug": "town-branch",
  "payment_provider": "mpesa"
}
```

The response contains router metadata, expiry, `.rsc` script, and one-time L2TP peer credentials. Never log or email the full response.

## Plans and subscribers

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/routers/{router_uid}/packages` | List or create router-scoped packages. |
| PATCH/DELETE | `/routers/{router_uid}/packages/{package_uid}` | Edit or retire a package. |
| GET/POST | `/routers/{router_uid}/hotspot-users` | List or provision Hotspot users. |
| POST | `/routers/{router_uid}/hotspot-users/{user_uid}/{enable|disable}` | Change Hotspot access. |
| DELETE | `/routers/{router_uid}/hotspot-users/{user_uid}` | Remove Hotspot access and DB record. |
| GET/POST | `/routers/{router_uid}/pppoe-users` | List or provision PPPoE users. |
| POST | `/routers/{router_uid}/pppoe-users/{user_uid}/{enable|disable}` | Change PPPoE access. |
| DELETE | `/routers/{router_uid}/pppoe-users/{user_uid}` | Remove PPPoE secret and DB record. |

Package request:

```json
{
  "name": "One hour",
  "description": "Hotspot access",
  "price": 10,
  "service_type": "hotspot",
  "validity_minutes": 60,
  "router_profile": "paid-1h",
  "rate_limit": "10M/10M",
  "is_active": true
}
```

## Public portal and payments

| Method | Path | Purpose |
|---|---|---|
| GET | `/public/portals/{portal_slug}` | Trusted portal name, provider, and active server-priced plans. |
| POST | `/public/portals/{portal_slug}/payments` | Start payment; requires unique `Idempotency-Key` header. |
| GET | `/public/payments/{payment_id}` | Poll status; requires `X-Payment-Token`. |
| POST | `/webhooks/mpesa/stk` | Safaricom callback. |
| POST | `/webhooks/kopokopo/incoming-payment` | Signed Kopo Kopo callback. |

Hotspot payment request:

```json
{
  "package_uid": "package-uuid",
  "phone_number": "0712345678"
}
```

For PPPoE renewal also send `"customer_reference": "existing-pppoe-username"`. The client never sends amount, router ID, RouterOS profile, callback URL, or provider credentials.

A `202` response returns `payment_id`, `status_token`, provider, masked phone, server amount, and expiry. Poll every 2–3 seconds and stop at expiry. Hotspot credentials are returned only after `provisioned` and only for the short credential window.

## Operations

| Method | Path | Purpose |
|---|---|---|
| GET | `/routers/{router_uid}/payments` | Completed, durable payment ledger. |
| GET | `/routers/{router_uid}/payment-sessions` | Pending, failed, review, and provisioned payment attempts. |
| GET | `/routers/{router_uid}/logs` | Router-scoped audit events with masked phones. |
| POST | `/payments/{payment_id}/retry-provisioning` | Retry paid sessions whose RouterOS activation failed. |
| POST | `/jobs/expire-access` | Superadmin manual maintenance run. Normal operation uses `jobs.py`. |
| GET | `/health/live` | Process liveness (outside versioned base). |
| GET | `/health/ready` | Database readiness (outside versioned base). |

The legacy unauthenticated `/stkpush/initiate` endpoint returns `410 Gone` and must not be used.
