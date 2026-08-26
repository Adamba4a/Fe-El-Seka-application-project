-- Spec 024: Groups — scope a ride to exactly one group (FR-006, FR-007, FR-008).
-- NULL = general feed, today's behavior, unchanged. ON DELETE SET NULL (not
-- CASCADE) so an archived/deleted group never deletes real ride history
-- (FR-021).

ALTER TABLE public.rides
    ADD COLUMN group_id UUID NULL REFERENCES public.groups(id) ON DELETE SET NULL;

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
