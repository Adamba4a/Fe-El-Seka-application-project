-- Fraud Signal Capture
-- Creates: fraud_signals table
-- One row per trust-relevant event (signup, login, ride posting, booking
-- creation), carrying a one-way HMAC-SHA256 hash of the device ID (when sent)
-- and the source IP — never the raw values. Internal fraud/trust telemetry,
-- not surfaced in any UI — RLS enabled, no public policies (service-role
-- backend access only), kept indefinitely (no retention job).
-- See specs/030-fraud-signal-capture/data-model.md.

-- ── fraud_signals ──────────────────────────────────────────────────────────

CREATE TABLE public.fraud_signals (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    event_type        TEXT NOT NULL CHECK (event_type IN ('signup', 'login', 'ride_posted', 'booking_created')),
    hashed_device_id  TEXT,
    hashed_ip         TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fraud_signals_hashed_device_id
    ON public.fraud_signals (hashed_device_id) WHERE hashed_device_id IS NOT NULL;

CREATE INDEX idx_fraud_signals_hashed_ip
    ON public.fraud_signals (hashed_ip);

CREATE INDEX idx_fraud_signals_user_created
    ON public.fraud_signals (user_id, created_at);

-- ── RLS ────────────────────────────────────────────────────────────────────
-- Internal fraud/trust telemetry, never surfaced in any passenger/driver/admin
-- UI. No public policies — only the backend service-role connection (asyncpg
-- pool) can read/write this table.

ALTER TABLE public.fraud_signals ENABLE ROW LEVEL SECURITY;
