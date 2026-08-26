-- Spec 024: Groups — deterministic membership/community substrate for scoping
-- ride discovery to focused communities (general/interest, company, university).
-- Creates: groups, domain_verifications, group_memberships.
--
-- Ordering: groups -> domain_verifications -> group_memberships, since
-- group_memberships.domain_verification_id references domain_verifications(id)
-- and group_memberships.group_id references groups(id).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── GROUPS ───────────────────────────────────────────────────────────────────

CREATE TABLE public.groups (
    id                       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name                     TEXT            NOT NULL,
    type                     TEXT            NOT NULL,
    description              TEXT,
    route_tags               TEXT[]          NOT NULL DEFAULT '{}',
    owner_id                 UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    domain                   TEXT            UNIQUE,
    invite_token             TEXT            NOT NULL UNIQUE DEFAULT replace(gen_random_uuid()::text, '-', ''),
    invite_token_revoked_at  TIMESTAMPTZ,
    -- Denormalized member count, maintained entirely by the trigger below
    -- (including the owner's own initial membership row) — default 0, never
    -- written to directly, so the trigger is the single source of truth and
    -- the owner's insert is not double-counted.
    member_count             INTEGER         NOT NULL DEFAULT 0,
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    archived_at              TIMESTAMPTZ,
    CONSTRAINT chk_groups_type          CHECK (type IN ('general', 'company', 'university')),
    CONSTRAINT chk_groups_name_length   CHECK (length(trim(name)) BETWEEN 3 AND 80),
    CONSTRAINT chk_groups_route_tags    CHECK (array_length(route_tags, 1) IS NULL OR array_length(route_tags, 1) <= 10),
    CONSTRAINT chk_groups_member_count  CHECK (member_count >= 0)
);

ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;

-- FR-003 — directory search by name (trigram) and by type/route_tags (GIN).
CREATE INDEX idx_groups_name_trgm ON public.groups USING gin (name gin_trgm_ops);
CREATE INDEX idx_groups_route_tags ON public.groups USING gin (route_tags);
CREATE INDEX idx_groups_type ON public.groups (type) WHERE archived_at IS NULL;

-- ── DOMAIN VERIFICATIONS ─────────────────────────────────────────────────────

CREATE TABLE public.domain_verifications (
    id                     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    email                  TEXT            NOT NULL,
    domain                 TEXT            NOT NULL,
    requested_group_type   TEXT            NOT NULL,
    otp_code_hash          TEXT            NOT NULL,
    otp_expires_at         TIMESTAMPTZ     NOT NULL,
    verified_at            TIMESTAMPTZ,
    -- True if `domain` had no prior successful (verified_at IS NOT NULL) row at
    -- request time — decides both whether confirming this row creates a new
    -- `groups` row, and is the rate-limit counting predicate (Research §3).
    is_first_for_domain    BOOLEAN         NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_domain_verifications_type CHECK (requested_group_type IN ('company', 'university'))
);

ALTER TABLE public.domain_verifications ENABLE ROW LEVEL SECURITY;

-- Used both to look up "has this domain ever been verified" (is_first_for_domain
-- computation) and for the new-domain rate-limit window query (Research §3).
CREATE INDEX idx_domain_verifications_domain ON public.domain_verifications (domain, verified_at);
CREATE INDEX idx_domain_verifications_user ON public.domain_verifications (user_id, created_at DESC);
CREATE INDEX idx_domain_verifications_first_for_domain
    ON public.domain_verifications (created_at)
    WHERE is_first_for_domain = true AND verified_at IS NOT NULL;

-- ── GROUP MEMBERSHIPS ────────────────────────────────────────────────────────

CREATE TABLE public.group_memberships (
    id                        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id                  UUID          NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    user_id                   UUID          NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role                      TEXT          NOT NULL DEFAULT 'member',
    domain_verification_id    UUID          REFERENCES public.domain_verifications(id),
    joined_at                 TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_group_memberships_role CHECK (role IN ('owner', 'member')),
    CONSTRAINT uq_group_memberships_group_user UNIQUE (group_id, user_id)
);

ALTER TABLE public.group_memberships ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_group_memberships_user ON public.group_memberships (user_id);

-- Denormalized groups.member_count maintenance — single source of truth for the
-- counter; see the column comment on public.groups.member_count above.
CREATE OR REPLACE FUNCTION public.groups_update_member_count() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE public.groups SET member_count = member_count + 1 WHERE id = NEW.group_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE public.groups SET member_count = member_count - 1 WHERE id = OLD.group_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_group_memberships_count
    AFTER INSERT OR DELETE ON public.group_memberships
    FOR EACH ROW EXECUTE FUNCTION public.groups_update_member_count();
