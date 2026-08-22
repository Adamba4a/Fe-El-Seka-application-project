-- Sets the real Instapay wallet-transfer number for manual top-ups. The
-- platform_settings row for 'vodafone_cash_number' was left holding the
-- "not configured" sentinel by 20260814000003 (no operator had set a real
-- value yet), which is why the top-up screen showed "Top-Up Temporarily
-- Unavailable". Reuses the existing vodafone_cash_number key even though
-- top-ups now go via Instapay — renaming the key would ripple through
-- wallet_topup_service.py and the frontend for no functional benefit.
INSERT INTO public.platform_settings (key, value, updated_at)
VALUES ('vodafone_cash_number', '01006346882', now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;
