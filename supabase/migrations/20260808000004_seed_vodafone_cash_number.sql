-- Phase 15 (interim): Manual Wallet Top-Up via Vodafone Cash
-- Seeds the platform's Vodafone Cash number as an admin-editable setting (FR-001),
-- reusing the existing platform_settings mechanism (mirrors support_email).
-- Placeholder value — a platform operator must update this to the real number
-- before launch, the same way support_email is maintained today (direct DB edit,
-- no settings-editor UI exists for either key).

INSERT INTO public.platform_settings (key, value)
VALUES ('vodafone_cash_number', '01000000000')
ON CONFLICT (key) DO NOTHING;
