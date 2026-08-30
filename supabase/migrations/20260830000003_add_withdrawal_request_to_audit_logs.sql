-- Spec 026: adds a nullable target-reference column so admin_audit_logs can
-- log withdrawal-request review actions, the same way it already
-- disambiguates wallet top-up review actions via topup_request_id.
-- No action_type CHECK change needed: 'approved'/'rejected' are already
-- valid values, reused as-is for this feature.

ALTER TABLE public.admin_audit_logs
    ADD COLUMN withdrawal_request_id UUID REFERENCES public.withdrawal_requests(id);
