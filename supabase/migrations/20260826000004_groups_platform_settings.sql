-- Spec 024: Groups — NFR-004/NFR-005 configurable thresholds via the existing
-- platform_settings key/value table (see 20260614000005_create_platform_settings.sql),
-- reusing the pattern already used by verification_service/_get_support_email
-- and wallet_topup_service/_get_vodafone_cash_number.

INSERT INTO public.platform_settings (key, value) VALUES
    -- FR-011: comma-separated public/personal email provider domains that can
    -- never qualify as a company/university domain. Seeded with the six named
    -- in the spec (at minimum) — admin-editable without a redeploy.
    ('group_domain_blocklist', 'gmail.com,yahoo.com,outlook.com,hotmail.com,icloud.com,protonmail.com'),
    -- Anti-abuse: max distinct users allowed to be first-to-register a brand-new
    -- domain within the window below (Research §3).
    ('group_new_domain_rate_limit', '5'),
    ('group_new_domain_rate_limit_window_minutes', '60')
ON CONFLICT (key) DO NOTHING;
