# Security Review

This document tracks the current security posture of the codebase. It is meant
to separate what has already been hardened from what still needs deeper
architectural work before a production launch.

## Fixed in this hardening pass

| Severity | Area | Status |
| --- | --- | --- |
| High | Messaging authorization | Fixed. Conversation membership is now enforced in chat service reads/writes and in the messaging WebSocket flow before participant fanout. |
| High | Call signaling authorization | Fixed. Signaling messages now validate database-backed call participation and active call state before join/offer/answer forwarding. |
| High | Password reset lifecycle | Fixed for the current single-instance design. Reset tokens now carry `jti`, are one-time use, and are bound to the user’s current password state. |
| Medium | Verification token replay | Fixed for the current single-instance design. Verification links are now tracked as used and rejected on replay. |
| Medium | File upload handling | Improved. Profile uploads now inspect file bytes, force a safe extension, and generate server-side filenames. |
| Medium | Public profile exposure | Improved. Public profile responses no longer expose email addresses. |
| Medium | Search result privacy | Improved. Search responses no longer return user email addresses. |
| Medium | Abuse protection | Improved. Login, resend-verification, forgot-password, reset-password, and verify-email flows now enforce basic in-memory rate limits. |
| Medium | CORS defaults | Fixed. Default origins are explicit, config validation rejects wildcard origins outside development, and app startup enforces the same rule. |
| Medium | Mobile OAuth token leakage | Fixed. Mobile OAuth redirects now hand off a short-lived exchange code instead of access and refresh tokens in the URL. |

## Remaining high-value gaps

### 1. WebSocket auth still uses query-string JWTs

- Location: [messaging_sdk/api/v1/chat.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/api/v1/chat.py), [messaging_sdk/api/v1/websocket_signaling.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/api/v1/websocket_signaling.py)
- Current state:
  - Call membership and conversation membership are now enforced.
  - The initial WebSocket authentication token is still supplied as `?token=...`.
- Risk:
  - Tokens may still leak through logs, browser history, monitoring tools, or reverse proxies.
- Recommended next step:
  - Move to a short-lived WebSocket session token, header-based handshake where supported, or a pre-authenticated connection bootstrap endpoint.

### 2. Token replay protection is process-local

- Location: [messaging_sdk/core/transient_store.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/core/transient_store.py)
- Current state:
  - One-time token tracking and rate limiting now exist, but they are backed by in-memory TTL stores.
- Risk:
  - In multi-worker or multi-instance deployments, replay protection and rate limits will not be shared across instances.
- Recommended next step:
  - Move transient security state to Redis or another shared store before horizontal scaling.

### 3. User discovery still matches on email internally

- Location: [messaging_sdk/services/search_service.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/services/search_service.py), [messaging_sdk/services/user_service.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/services/user_service.py)
- Current state:
  - Public responses no longer return email addresses.
  - Search relevance and direct user lookup still use email as an internal match field.
- Risk:
  - Attackers may still infer account presence through search behavior or lookup workflows.
- Recommended next step:
  - Decide whether email-based discovery should exist at all. If not, remove email from public search matching and keep it only for explicit account recovery/auth flows.

### 4. Uploads are still served from the application origin

- Location: [messaging_sdk/api/v1/profile.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/api/v1/profile.py), [messaging_sdk/__init__.py](c:/Users/User/Desktop/messaging-and-calling-backend/messaging_and_calling_backend/messaging_sdk/__init__.py)
- Current state:
  - File type validation and safe naming are now in place.
  - Uploaded assets are still served under `/uploads` from the same application origin.
- Risk:
  - Serving untrusted user content from the app origin remains a broader isolation risk.
- Recommended next step:
  - Move user uploads to object storage or a separate asset domain with restrictive content headers.

## Operational guidance

- Treat the current replay-protection and rate-limit implementation as suitable for local development and single-instance deployments only.
- Do not enable wildcard CORS origins outside development.
- Keep JWT secrets, OAuth credentials, and email provider credentials out of source control and rotate them if exposure is suspected.
- Before a public launch, prioritize replacing process-local transient security state and redesigning WebSocket authentication transport.
