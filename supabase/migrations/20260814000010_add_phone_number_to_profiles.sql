-- Spec 020: required plain-text phone_number (never SMS-verified).
-- Nullable at the DB layer — required-ness is enforced at the application
-- layer so legacy rows are never broken by this migration.
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS phone_number TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_profiles_phone_number_format'
  ) THEN
    ALTER TABLE profiles ADD CONSTRAINT chk_profiles_phone_number_format
        CHECK (phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{6,14}$');
  END IF;
END $$;

-- Cleanup: some local dev environments carry leftover schema from the
-- abandoned/never-merged Spec 019 (phone-as-alternate-identifier) branch.
-- Spec 020 explicitly requires phone_number to carry NO uniqueness
-- constraint (FR-011) and email to remain the sole sign-in identifier
-- (FR-001), so any such residue must not survive this migration.
DROP INDEX IF EXISTS uq_profiles_phone_number;
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS chk_profiles_has_identifier;
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS chk_phone_number_e164;
