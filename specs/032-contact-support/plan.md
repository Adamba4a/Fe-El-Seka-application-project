# Implementation Plan: Contact Support

## Architecture and constitution check
Use existing Next.js 14 apps and FastAPI with asyncpg. Backend owns validation, rate limits, status transitions and delivery. UUID entities and private RLS tables protect contact data. Status history is append-only. No changes to transport/ride business rules.

## Data model
support_requests: id UUID, email, description, locale, client IP fingerprint, status, email_status, email_attempts, next_email_attempt_at, created_at, updated_at.
support_status_history: id UUID, request_id, admin_id, old_status, new_status, created_at.
Rate limits use a database advisory lock to serialize checking and inserting. Retain only a keyed IP digest, not raw addresses, using the server service-role secret as HMAC key.

## API contract
- POST /api/support: public; JSON {id UUID, email string, description string, locale en|ar, website string (honeypot)}. 201 {id}; 422 validation; 429 throttled. Existing ID returns only {id}, never report content.
- GET /api/admin/support?status=open|in_progress|resolved&page=1: admin only; 20 items plus total/page. Omitted status lists all. No IP digest exposed.
- PATCH /api/admin/support/{id}: admin only; {status}; returns {id,status}; 404 absent. Update and status history in one transaction.

## Delivery
Dedicated support queue columns on the report. Poll every 60 seconds, claim due rows with FOR UPDATE SKIP LOCKED, send with existing transport and a 20-second bound, mark sent or retry (1m, 5m, 30m, 2h; fail after five attempts). Keep delivery separate from submission. Fixed recipient configurable through SUPPORT_EMAIL, default agreed inbox.

## Frontend
Mount a native dialog in the main root translation provider for all routes. Preserve the underlying signup state and draft. Localized client validation and server error mapping. Fixed launcher above bottom navigation, logical inline positioning. Admin support inbox uses existing authentication client and navigation.

## Verification
Model validation, public API/admin authorization, idempotency/rate-limit behavior, email failure/retry and HTML escaping tests. Typecheck both apps; targeted lint. Compare translation key parity and scan hardcoded UI strings. Browser-check dialog when local runtime is available.
