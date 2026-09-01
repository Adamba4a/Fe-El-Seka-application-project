-- Spec 028: Loyalty Points. Generalizes the driver-only car-maintenance savings
-- ledger (driver_wallets.car_maintenance_savings_egp + car_maintenance_rewards,
-- see 20260820000002_car_maintenance_rewards.sql) into a role-agnostic points
-- system usable by both passengers and drivers (research.md Decisions 1-2).
-- car_maintenance_savings_egp / car_maintenance_rewards are left in place as a
-- deprecated archival record, not dropped.

-- ── Enums ───────────────────────────────────────────────────────────────────

CREATE TYPE loyalty_account_role AS ENUM ('passenger', 'driver');

CREATE TYPE loyalty_transaction_reason AS ENUM (
    'ride_completed_earn',
    'redemption_spend',
    'redemption_refund',
    'ride_reversal_clawback',
    'admin_adjustment'
);

CREATE TYPE loyalty_reward_type AS ENUM ('free_ride', 'discount', 'car_maintenance', 'voucher');

CREATE TYPE loyalty_audience AS ENUM ('passenger', 'driver', 'both');

CREATE TYPE loyalty_fulfillment_mode AS ENUM ('instant', 'manual');

CREATE TYPE loyalty_redemption_status AS ENUM ('pending', 'fulfilled', 'rejected');

-- ── loyalty_points_accounts ────────────────────────────────────────────────

CREATE TABLE public.loyalty_points_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role loyalty_account_role NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, role)
);

CREATE INDEX idx_loyalty_points_accounts_user_id ON public.loyalty_points_accounts(user_id);

ALTER TABLE public.loyalty_points_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_read_own_loyalty_account
    ON public.loyalty_points_accounts
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

-- ── loyalty_points_transactions ────────────────────────────────────────────

CREATE TABLE public.loyalty_points_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.loyalty_points_accounts(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    reason loyalty_transaction_reason NOT NULL,
    ride_id UUID NULL REFERENCES public.rides(id),
    booking_id UUID NULL REFERENCES public.bookings(id),
    redemption_request_id UUID NULL,
    balance_after INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_loyalty_points_transactions_account_created
    ON public.loyalty_points_transactions(account_id, created_at DESC);

ALTER TABLE public.loyalty_points_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_read_own_loyalty_transactions
    ON public.loyalty_points_transactions
    FOR SELECT
    TO authenticated
    USING (
        account_id IN (
            SELECT id FROM public.loyalty_points_accounts WHERE user_id = auth.uid()
        )
    );

-- ── loyalty_reward_catalog ──────────────────────────────────────────────────

CREATE TABLE public.loyalty_reward_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type loyalty_reward_type NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    audience loyalty_audience NOT NULL,
    point_cost INTEGER NOT NULL CHECK (point_cost > 0),
    fulfillment_mode loyalty_fulfillment_mode NOT NULL DEFAULT 'instant',
    active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID NULL REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_loyalty_reward_catalog_audience_active
    ON public.loyalty_reward_catalog(audience, active);

ALTER TABLE public.loyalty_reward_catalog ENABLE ROW LEVEL SECURITY;

CREATE POLICY authenticated_read_active_catalog
    ON public.loyalty_reward_catalog
    FOR SELECT
    TO authenticated
    USING (active = true);

-- ── loyalty_redemption_requests ─────────────────────────────────────────────

CREATE TABLE public.loyalty_redemption_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.loyalty_points_accounts(id) ON DELETE CASCADE,
    catalog_entry_id UUID NOT NULL REFERENCES public.loyalty_reward_catalog(id),
    points_spent INTEGER NOT NULL,
    fulfillment_mode loyalty_fulfillment_mode NOT NULL,
    status loyalty_redemption_status NOT NULL DEFAULT 'pending',
    ride_id UUID NULL REFERENCES public.rides(id),
    booking_id UUID NULL REFERENCES public.bookings(id),
    fulfilled_by UUID NULL REFERENCES public.profiles(id),
    fulfilled_at TIMESTAMPTZ NULL,
    rejection_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_loyalty_redemption_requests_pending
    ON public.loyalty_redemption_requests(status, created_at ASC)
    WHERE status = 'pending';

CREATE INDEX idx_loyalty_redemption_requests_account_id
    ON public.loyalty_redemption_requests(account_id);

ALTER TABLE public.loyalty_redemption_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_read_own_loyalty_redemptions
    ON public.loyalty_redemption_requests
    FOR SELECT
    TO authenticated
    USING (
        account_id IN (
            SELECT id FROM public.loyalty_points_accounts WHERE user_id = auth.uid()
        )
    );

-- Deferred FK: loyalty_points_transactions.redemption_request_id, added now that
-- loyalty_redemption_requests exists.
ALTER TABLE public.loyalty_points_transactions
    ADD CONSTRAINT loyalty_points_transactions_redemption_request_id_fkey
        FOREIGN KEY (redemption_request_id) REFERENCES public.loyalty_redemption_requests(id);

-- ── admin_audit_logs extension (research.md Decision 9) ────────────────────

ALTER TABLE public.admin_audit_logs
    ADD COLUMN redemption_request_id UUID NULL REFERENCES public.loyalty_redemption_requests(id);

-- ── notification_event_type extension (research.md Decision 9) ─────────────

ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'loyalty_points_earned';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'loyalty_redemption_fulfilled';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'loyalty_redemption_rejected';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'loyalty_threshold_reached';

-- ── platform_settings seeds (research.md Decision 3/7, data-model.md) ──────

INSERT INTO public.platform_settings (key, value) VALUES
    ('loyalty_free_ride_point_cost', '500'),
    ('loyalty_free_ride_max_fare_egp', '100.00'),
    ('loyalty_discount_point_cost', '200'),
    ('loyalty_discount_percentage', '10'),
    ('loyalty_car_maintenance_point_cost', '3000'),
    ('loyalty_passenger_earn_points_per_egp_fare', '1')
ON CONFLICT (key) DO NOTHING;

-- ── loyalty_reward_catalog system entries (singletons) ──────────────────────
-- point_cost mirrors the platform_settings values above at seed time
-- (research.md Decision 3 — admin edits keep both in sync going forward).

INSERT INTO public.loyalty_reward_catalog (type, title, description, audience, point_cost, fulfillment_mode)
VALUES
    ('free_ride', 'Free Ride', 'Redeem points to cap your fare on your next ride.', 'passenger', 500, 'instant'),
    ('discount', 'Fare Discount', 'Redeem points for a percentage discount on your next ride.', 'passenger', 200, 'instant'),
    ('car_maintenance', 'Free Car Maintenance', 'Redeem accumulated points for free car maintenance, arranged by the Triplyy team.', 'driver', 3000, 'manual');

-- ── Data migration: existing car-maintenance state → loyalty ledger ────────
-- (research.md Decision 2) 1:1 conversion of each driver's accumulated
-- car_maintenance_savings_egp into a loyalty_points_accounts(role='driver')
-- balance, and of any still-open PENDING car_maintenance_rewards row into a
-- pending loyalty_redemption_requests row. Already-FULFILLED rows stay in
-- car_maintenance_rewards as archival history and are not migrated.

INSERT INTO public.loyalty_points_accounts (user_id, role, balance)
SELECT w.driver_id, 'driver'::loyalty_account_role, FLOOR(w.car_maintenance_savings_egp)::INTEGER
FROM public.driver_wallets w
WHERE w.car_maintenance_savings_egp > 0
ON CONFLICT (user_id, role) DO UPDATE
    SET balance = public.loyalty_points_accounts.balance + EXCLUDED.balance;

-- Ensure an account row also exists for any driver who has a PENDING reward
-- but zero *current* savings (the counter resets to 0 once a reward is
-- granted, so this driver may not have been covered by the insert above).
INSERT INTO public.loyalty_points_accounts (user_id, role, balance)
SELECT DISTINCT r.driver_id, 'driver'::loyalty_account_role, 0
FROM public.car_maintenance_rewards r
WHERE r.status = 'PENDING'
ON CONFLICT (user_id, role) DO NOTHING;

WITH car_maintenance_entry AS (
    SELECT id FROM public.loyalty_reward_catalog WHERE type = 'car_maintenance'
)
INSERT INTO public.loyalty_redemption_requests
    (account_id, catalog_entry_id, points_spent, fulfillment_mode, status, created_at)
SELECT
    a.id,
    ce.id,
    FLOOR(r.amount_egp)::INTEGER,
    'manual'::loyalty_fulfillment_mode,
    'pending'::loyalty_redemption_status,
    r.reached_at
FROM public.car_maintenance_rewards r
JOIN public.loyalty_points_accounts a ON a.user_id = r.driver_id AND a.role = 'driver'
CROSS JOIN car_maintenance_entry ce
WHERE r.status = 'PENDING';
