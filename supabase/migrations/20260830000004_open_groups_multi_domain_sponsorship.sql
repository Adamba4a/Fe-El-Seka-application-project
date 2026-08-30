-- Groups redesign: remove the general/company/university type distinction —
-- every group is now open, free-join for any org-verified user (Spec 025 is
-- the platform's sole trust floor). Domain verification no longer creates or
-- gates membership in a group; it now only proves a member's email domain
-- against a *specific sponsored group's* configured domain list, so that
-- group becomes eligible for funded (not cash) rides for that member.
--
-- This also fixes the sponsorship fragmentation bug: previously a sponsored
-- group was tied to exactly one domain (e.g. `eng-st.cu.edu.eg`), splitting
-- students of the same university across faculty subdomains into separate
-- groups even though they ride the same routes. group_sponsor_domains lets
-- one sponsored group list many eligible domains.

-- ── GROUP_SPONSOR_DOMAINS ────────────────────────────────────────────────────

CREATE TABLE public.group_sponsor_domains (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id    UUID          NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    domain      TEXT          NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    -- A domain can be claimed by at most one sponsored group at a time —
    -- otherwise which group's funded balance would a verifier's rides draw
    -- from is ambiguous. One group, however, may claim many domains.
    CONSTRAINT uq_group_sponsor_domains_domain UNIQUE (domain)
);

CREATE INDEX idx_group_sponsor_domains_group_id ON public.group_sponsor_domains (group_id);

ALTER TABLE public.group_sponsor_domains ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_read_group_sponsor_domains" ON public.group_sponsor_domains
    FOR SELECT
    TO authenticated
    USING (true);

-- Backfill: every existing sponsored group's single `domain` becomes its
-- first row here before the column is dropped below.
INSERT INTO public.group_sponsor_domains (group_id, domain)
SELECT id, domain FROM public.groups
WHERE domain IS NOT NULL AND is_sponsored = true;

-- ── GROUPS: drop the type/domain-ownership model ────────────────────────────

ALTER TABLE public.groups DROP CONSTRAINT IF EXISTS chk_groups_sponsored_type;
ALTER TABLE public.groups DROP CONSTRAINT IF EXISTS chk_groups_type_domain;
ALTER TABLE public.groups DROP CONSTRAINT IF EXISTS chk_groups_type;
DROP INDEX IF EXISTS idx_groups_type;

ALTER TABLE public.groups DROP COLUMN type;
ALTER TABLE public.groups DROP COLUMN domain;

-- ── DOMAIN_VERIFICATIONS: re-scope from "creates/joins a domain-owned group"
-- to "proves eligibility against one sponsored group's domain list" ────────

ALTER TABLE public.domain_verifications DROP CONSTRAINT IF EXISTS chk_domain_verifications_type;
DROP INDEX IF EXISTS idx_domain_verifications_first_for_domain;

ALTER TABLE public.domain_verifications DROP COLUMN requested_group_type;
ALTER TABLE public.domain_verifications DROP COLUMN is_first_for_domain;

-- Nullable: the org-only-access gate (Spec 025) still inserts rows here with
-- no group intent (org_access_service.py) — only a Groups sponsorship-
-- eligibility request sets this.
ALTER TABLE public.domain_verifications
    ADD COLUMN group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE;

CREATE INDEX idx_domain_verifications_group_domain ON public.domain_verifications (group_id, domain);
