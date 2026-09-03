# Phase 0 Research: Fraud Signal Capture

## R1: Fire-and-forget mechanism — FastAPI `BackgroundTasks`, not `asyncio.create_task`

**Decision**: Use FastAPI's `BackgroundTasks` (`background_tasks.add_task(fraud_signal_service.record_signal, ...)`),
injected as a handler parameter, exactly as `match_logging_service.persist_match_events` is already called from
`services/api/app/api/search/router.py` (`background_tasks.add_task(match_logging_service.persist_match_events, ...)`).

**Rationale**: This is the actual, verified mechanism for request-triggered best-effort logging elsewhere in the
codebase — confirmed by reading `search/router.py` directly, not assumed from the spec's own wording. (Note:
029-driver-gps-trace-history used `asyncio.create_task` instead for GPS pings; that was a deliberate choice for a
high-frequency ping endpoint with no natural `BackgroundTasks`-carrying request/response cycle shape difference, but
it is not the more common pattern in this codebase. This feature follows `match_logging_service`'s precedent instead,
since the spec explicitly names it and the four target endpoints are already ordinary request/response handlers.)

**Alternatives considered**:
- `asyncio.create_task` (029's mechanism) — rejected: no reason to diverge from the closer, explicitly-named
  precedent (`persist_match_events`) for these four ordinary request handlers.

---

## R2: Hashing mechanism

**Decision**: HMAC-SHA256 (Python stdlib `hmac` + `hashlib`, no new dependency) over each raw value (device ID,
IP address), keyed by a single server-side secret read from `Settings` (`app/core/config.py`), the same way
`internal_secret` is already loaded there (env-file-backed `pydantic-settings` field, no Supabase Vault indirection
currently used for backend-only secrets in this codebase).

**Rationale**: HMAC-SHA256 is deterministic per (secret, input) pair — required for FR-008/graph-linking (the same
device/IP must hash identically across requests and accounts) — and is infeasible to reverse without the secret,
satisfying FR-003/NFR-003. Using the stdlib avoids adding a new dependency for a single-purpose keyed hash.

**Alternatives considered**:
- Bare SHA-256 (no key) — rejected: reversible via rainbow table for the small, guessable space of IPv4 addresses
  and any device-ID scheme with low entropy; FR-008 explicitly requires a server-side secret.
- Supabase Vault-stored secret — rejected: no existing backend code path reads secrets from Vault (Vault is used
  for `firebase_service_account_secret_name`-style storage-object secrets, not simple config values); a new
  `pydantic-settings` field (`fraud_signal_hmac_secret`) matches how `internal_secret`/`webhook_secret` are already
  handled, avoiding a new secrets-loading mechanism for one value.

---

## R3: Client IP extraction

**Decision**: `request.client.host` (FastAPI/Starlette `Request` object), used as-is.

**Rationale**: `services/api/Dockerfile` already starts uvicorn with `--proxy-headers --forwarded-allow-ips=*`
(confirmed by reading the Dockerfile CMD directly), which makes uvicorn itself parse the `X-Forwarded-For` header
from the (trusted) reverse proxy and rewrite `request.client.host` to the real client IP before the request ever
reaches application code. No manual header parsing is needed or should be added — doing so would duplicate
uvicorn's own trusted-proxy handling and risk trusting an untrusted client-supplied header instead.

**Alternatives considered**:
- Manually reading `X-Forwarded-For` in the handler — rejected: redundant with, and less trustworthy than, uvicorn's
  own `--proxy-headers` handling (a client could set `X-Forwarded-For` directly if the app trusted it instead of
  relying on uvicorn's proxy-boundary parsing).

---

## R4: Device identifier transport

**Decision**: A new request header, `X-Device-Id`, read via FastAPI `Request.headers.get("x-device-id")` in each
of the four instrumented handlers. Optional — absent header means the hashed-device field is stored null (per spec
Edge Cases), never blocks the request.

**Rationale**: No existing device-identifier convention exists anywhere in the codebase (verified: no
`X-Device-Id`/`device_id` header handling found in `services/api/app`). A dedicated header (rather than a body
field) keeps the signal orthogonal to each endpoint's existing Pydantic request models — FR-001's four events don't
share a request schema today, and a header lets one client-side interceptor attach the identifier uniformly to all
outgoing requests without four separate per-endpoint client code paths.

**Alternatives considered**:
- Adding a `device_id` field to each of the four endpoints' Pydantic request bodies — rejected: four separate model
  changes for the same cross-cutting concern, and would need to be threaded through every future instrumented
  endpoint the same way; a header is a one-time client interceptor addition instead.

---

## R5: Client-side device identifier generation — out of scope for this plan

**Decision**: This plan covers `services/api` only (per spec Affected Applications / Out-of-Scope). Generating and
persisting a stable per-install identifier client-side (`apps/main`), and attaching it as `X-Device-Id` on the four
instrumented request types, is a small, separate frontend change tracked as a follow-up task in `tasks.md` rather
than invented here — this plan documents the backend contract (header name, optional-ness) the frontend change must
satisfy.

**Rationale**: `services/api` is a shared backend used by `apps/main` only for these flows (no separate driver app
per Principle VII's actual monorepo shape — passenger/driver are role-routed within `apps/main`). Backend and
frontend changes are still sequenced as distinct tasks for review clarity, matching how 029 kept
`services/api`-only scope explicit.

---

## R6: Google OAuth sign-in is not backend-observable as a discrete "login" event

**Decision**: No signal record is generated for Google OAuth sign-in. Documented as a known gap, not addressed by
this feature.

**Rationale**: Confirmed by searching `services/api/app/api` for any Google/OAuth-handling route — none exists.
Per `project_auth_overhaul` memory, Google sign-in is a client-side Supabase Auth SDK flow; the backend only ever
sees the resulting session token on subsequent authenticated requests (`get_current_user`), with no discrete
"a login just happened via Google" event to hang a signal record on. `sign_in_with_password` (password login) and
`verify_otp` (OTP-once, which establishes the account on first use per spec FR-001's "signup" event) remain fully
covered — this gap is scoped to the one OAuth path.

**Alternatives considered**:
- Treating the first authenticated request after a Google sign-in as a proxy "login" event — rejected: no reliable
  way to distinguish "just logged in via Google" from "already-authenticated request", would require session-state
  tracking well beyond this feature's scope (out-of-scope per spec: "any user-visible indication" and no new
  session-tracking infrastructure named in Dependencies).
