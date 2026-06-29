-- Phase 8: Financial System — immutable driver ledger
-- Creates: ledger_entry_type enum, driver_ledger_entries table
-- Append-only financial audit trail. UPDATE and DELETE are revoked from all client roles.
-- All writes use service role (backend only); reads are filtered per driver by RLS.
--
-- Entry types:
--   COMMISSION_DEBIT — commission deducted from driver wallet on ride completion (per confirmed booking)
--   ADMIN_CREDIT     — admin manual top-up (cash/bank transfer confirmed offline)
--   ADMIN_DEBIT      — admin corrective debit (reversal of erroneous top-up)
--
-- Sign convention: amount_egp is always stored positive.
--   ADMIN_CREDIT     → balance_egp += amount_egp
--   COMMISSION_DEBIT → balance_egp -= amount_egp
--   ADMIN_DEBIT      → balance_egp -= amount_egp
--
-- Commission formula (COMMISSION_DEBIT entries only):
--   amount_egp = ROUND(fuel_cost_egp_snapshot * 0.20 / total_seats_at_ride_creation, 2)
--   The 20% rate is the same fixed constant used in Phase 5 pricing (FR-025, FR-027).

CREATE TYPE ledger_entry_type AS ENUM (
    'COMMISSION_DEBIT',
    'ADMIN_CREDIT',
    'ADMIN_DEBIT'
);

CREATE TABLE public.driver_ledger_entries (
    id                      UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id               UUID                NOT NULL REFERENCES public.driver_wallets(id) ON DELETE RESTRICT,
    driver_id               UUID                NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    type                    ledger_entry_type   NOT NULL,
    amount_egp              NUMERIC(10, 2)      NOT NULL,
    -- Ride and booking context (COMMISSION_DEBIT entries only)
    ride_id                 UUID                REFERENCES public.rides(id) ON DELETE RESTRICT,
    booking_id              UUID                REFERENCES public.bookings(id) ON DELETE RESTRICT,
    -- Snapshot of ride.price_per_seat * total_seats / 1.20 at time of deduction.
    -- Provides full auditability: rate is hardcoded 20%, so fuel_cost_snapshot alone is sufficient.
    fuel_cost_egp_snapshot  NUMERIC(10, 2),
    -- Admin context (ADMIN_CREDIT / ADMIN_DEBIT entries only)
    created_by              UUID                REFERENCES public.profiles(id) ON DELETE RESTRICT,
    note                    TEXT,
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ledger_amount_non_negative CHECK (amount_egp >= 0.00)
);

-- ── Immutability enforcement ──────────────────────────────────────────────────
-- Default privileges grant ALL to authenticated (from 20260614000008_grants.sql).
-- Revoke UPDATE and DELETE so no client role can modify ledger rows.
REVOKE UPDATE, DELETE ON public.driver_ledger_entries FROM authenticated, anon;

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Primary query: driver transaction history (newest-first, paginated)
CREATE INDEX idx_driver_ledger_driver_created
    ON public.driver_ledger_entries (driver_id, created_at DESC);

-- Audit lookup: all ledger entries for a specific ride
CREATE INDEX idx_driver_ledger_ride_id
    ON public.driver_ledger_entries (ride_id)
    WHERE ride_id IS NOT NULL;

-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE public.driver_ledger_entries ENABLE ROW LEVEL SECURITY;

-- Drivers read their own ledger entries only; no INSERT/UPDATE/DELETE for clients
CREATE POLICY "driver_read_own_ledger" ON public.driver_ledger_entries
    FOR SELECT USING (driver_id = auth.uid());

-- No client INSERT/UPDATE/DELETE: backend service role only
-- UPDATE/DELETE additionally blocked at privilege level (REVOKE above)
