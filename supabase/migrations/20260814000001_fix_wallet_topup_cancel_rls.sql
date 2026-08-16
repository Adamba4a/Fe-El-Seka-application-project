-- Fix: wallet_topup_requests driver-cancel RLS policy was missing an explicit
-- WITH CHECK clause. Without one, Postgres reuses the USING expression for
-- WITH CHECK on UPDATE, so a driver could issue a client-side UPDATE that
-- changes amount_egp / payment_reference / screenshot_path while leaving
-- status = 'PENDING' — the new row still satisfies
-- (driver_id = auth.uid() AND status = 'PENDING'), so the update was allowed.
-- That let a driver arbitrarily inflate an already-submitted amount before an
-- admin approves it.
--
-- Fix mirrors the existing "self-cancel" RLS pattern already used elsewhere in
-- this codebase (see 20260624000001_phase6_bookings.sql's
-- passenger_cancel_own_bookings policy): the WITH CHECK forces every
-- client-permitted UPDATE to land the row in the terminal CANCELLED state, so
-- a driver can no longer leave a PENDING row sitting in a client-mutated state.

DROP POLICY IF EXISTS "driver_cancel_own_topup_request" ON public.wallet_topup_requests;

CREATE POLICY "driver_cancel_own_topup_request" ON public.wallet_topup_requests
    FOR UPDATE USING (driver_id = auth.uid() AND status = 'PENDING')
    WITH CHECK (driver_id = auth.uid() AND status = 'CANCELLED');
