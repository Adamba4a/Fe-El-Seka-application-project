-- Spec 024: Groups — RLS policies.
-- All writes to groups/group_memberships/domain_verifications go through the
-- FastAPI backend's service-role connection (bypasses RLS), matching the
-- existing pattern (see 20260808000001_create_wallet_topup_requests.sql).
-- These policies are defense-in-depth for any direct client access.

-- ── GROUPS ───────────────────────────────────────────────────────────────────
-- FR-003: directory browsing/search is open to any authenticated user,
-- membership not required. No client write policies — group creation,
-- editing, archival, and ownership transfer are all service-role operations.

CREATE POLICY "authenticated_read_groups" ON public.groups
    FOR SELECT
    TO authenticated
    USING (true);

-- ── GROUP MEMBERSHIPS ────────────────────────────────────────────────────────
-- A user may read their own membership rows, and a group's owner may read all
-- of that group's membership rows (for member-management UI). No client write
-- policies — join/leave/remove/transfer all go through the backend.

CREATE POLICY "read_own_or_owned_group_memberships" ON public.group_memberships
    FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM public.groups
            WHERE groups.id = group_memberships.group_id
              AND groups.owner_id = auth.uid()
        )
    );

-- ── DOMAIN VERIFICATIONS ─────────────────────────────────────────────────────
-- Contains a hashed OTP and a real email address — least-privilege: a user may
-- only read or create their own verification attempts, never another user's.

CREATE POLICY "read_own_domain_verifications" ON public.domain_verifications
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "insert_own_domain_verifications" ON public.domain_verifications
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());
