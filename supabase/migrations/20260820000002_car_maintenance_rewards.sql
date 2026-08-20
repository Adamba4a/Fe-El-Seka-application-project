-- Car maintenance savings program: the 0.3 EGP/km distance fee that riders pay is
-- accumulated per-driver in driver_wallets.car_maintenance_savings_egp. When a driver's
-- accumulated savings reach CAR_MAINTENANCE_THRESHOLD_EGP (3000.00, see
-- commission_service.py), a car_maintenance_rewards row is created and the counter
-- resets to 0.00. Admin manually marks the reward fulfilled after arranging the
-- maintenance offline — there is no automated payout.

ALTER TABLE public.driver_wallets
    ADD COLUMN car_maintenance_savings_egp NUMERIC(10, 2) NOT NULL DEFAULT 0.00;

CREATE TABLE public.car_maintenance_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL REFERENCES public.driver_wallets(id) ON DELETE CASCADE,
    amount_egp NUMERIC(10, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'FULFILLED')),
    reached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fulfilled_at TIMESTAMPTZ NULL,
    fulfilled_by UUID NULL REFERENCES public.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_car_maintenance_rewards_driver_id ON public.car_maintenance_rewards(driver_id);
CREATE INDEX idx_car_maintenance_rewards_status ON public.car_maintenance_rewards(status);

ALTER TABLE public.car_maintenance_rewards ENABLE ROW LEVEL SECURITY;

CREATE POLICY driver_read_own_car_maintenance_rewards
    ON public.car_maintenance_rewards
    FOR SELECT
    TO authenticated
    USING (driver_id = auth.uid());

ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'car_maintenance_earned';

ALTER TABLE public.admin_audit_logs
    ADD COLUMN car_maintenance_reward_id UUID NULL REFERENCES public.car_maintenance_rewards(id);
