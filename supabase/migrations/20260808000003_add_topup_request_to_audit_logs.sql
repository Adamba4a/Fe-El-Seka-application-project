-- Phase 15 (interim): Manual Wallet Top-Up via Vodafone Cash
-- Adds a nullable target-reference column so admin_audit_logs can log wallet
-- top-up review actions (approve/reject/unlock), the same way it already
-- disambiguates identity-verification actions via submission_id.
-- No action_type CHECK change needed: 'approved'/'rejected'/'unlocked' are
-- already valid values, reused as-is for this feature (FR-013).

ALTER TABLE public.admin_audit_logs
    ADD COLUMN topup_request_id UUID REFERENCES public.wallet_topup_requests(id);
