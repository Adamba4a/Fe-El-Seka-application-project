-- Fix: the T004 seed inserted '01000000000' as the vodafone_cash_number
-- placeholder. That string is a validly-formatted Egyptian mobile number, so a
-- driver has no way to tell "this is a real platform number" from "nobody has
-- configured this yet" — if launch ships before an operator edits this row
-- (direct DB edit is the only mechanism today, per research.md §7), drivers
-- would be shown a plausible-looking number and could send real money to it.
--
-- Replace with an obviously-invalid sentinel so an unconfigured platform fails
-- loudly (a clearly-broken value on the submit form) instead of silently
-- looking legitimate. Only touches the row if it still holds the old
-- placeholder, so this is a no-op if an operator already set the real number.

UPDATE public.platform_settings
SET value = 'VODAFONE_CASH_NUMBER_NOT_CONFIGURED', updated_at = now()
WHERE key = 'vodafone_cash_number' AND value = '01000000000';
