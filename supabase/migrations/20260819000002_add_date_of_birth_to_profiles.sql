-- Spec 021: deferred identity verification (progressive KYC).
-- date_of_birth is collected at signup for new accounts only. Nullable at
-- the DB layer — pre-existing accounts are permanently exempt (FR-017) and
-- will never have a value, so no backfill is performed and no NOT NULL/
-- minimum-age constraint is applied here. Minimum-age validation happens
-- once, at signup, in the application layer (services/api profile_service).
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS date_of_birth DATE;
