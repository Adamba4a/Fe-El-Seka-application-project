-- Organization-Only Access Gate (Spec 025)
-- Adds the source-of-truth columns for the org-email access gate, relaxes
-- domain_verifications.requested_group_type so this feature's OTP rows
-- (which have no group intent) can be inserted, and backfills accounts that
-- already verified a domain through Groups (Spec 024) so they aren't
-- re-gated.

ALTER TABLE profiles
    ADD COLUMN org_verified_at TIMESTAMPTZ,
    ADD COLUMN org_verified_domain TEXT;

ALTER TABLE domain_verifications
    ALTER COLUMN requested_group_type DROP NOT NULL;

ALTER TABLE domain_verifications
    DROP CONSTRAINT chk_domain_verifications_type;

ALTER TABLE domain_verifications
    ADD CONSTRAINT chk_domain_verifications_type
    CHECK (requested_group_type IS NULL OR requested_group_type IN ('company', 'university'));

UPDATE profiles
SET org_verified_at = sub.verified_at,
    org_verified_domain = sub.domain
FROM (
    SELECT DISTINCT ON (user_id) user_id, domain, verified_at
    FROM domain_verifications
    WHERE verified_at IS NOT NULL
    ORDER BY user_id, verified_at ASC
) sub
WHERE profiles.id = sub.user_id;
