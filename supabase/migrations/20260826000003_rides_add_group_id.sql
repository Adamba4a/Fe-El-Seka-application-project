-- Spec 024: Groups — scope a ride to exactly one group (FR-006, FR-007, FR-008).
-- NULL = general feed, today's behavior, unchanged. Groups are soft-deleted
-- only (archived_at, FR-021) — the service layer never hard-deletes a groups
-- row. ON DELETE RESTRICT enforces that at the DB level too: SET NULL would
-- silently turn every one of a deleted group's private rides into a
-- publicly-visible general-feed ride (group_id IS NULL is the public-feed
-- flag), and CASCADE would destroy real ride history. RESTRICT just blocks
-- the hard delete outright, forcing the archive path instead.

ALTER TABLE public.rides
    ADD COLUMN group_id UUID NULL REFERENCES public.groups(id) ON DELETE RESTRICT;

CREATE INDEX idx_rides_group_id ON public.rides (group_id) WHERE group_id IS NOT NULL;

-- Additive SELECT policy for group-scoped rides (FR-007): Postgres OR's
-- multiple permissive policies together, so this broadens the existing
-- "driver_read_own_rides" policy to also let any member of a ride's group
-- read that ride, without needing to touch the existing policy definition.
CREATE POLICY "group_members_read_group_rides" ON public.rides
    FOR SELECT
    TO authenticated
    USING (
        group_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM public.group_memberships
            WHERE group_memberships.group_id = rides.group_id
              AND group_memberships.user_id = auth.uid()
        )
    );
