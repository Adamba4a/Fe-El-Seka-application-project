-- spatial_ref_sys is a PostGIS system table (SRID/projection reference
-- metadata, auto-installed by the postgis extension), not application data.
-- It ships without RLS, which the Supabase security advisor flags since it's
-- then fully exposed to the anon/authenticated roles. It holds no sensitive
-- or user-owned data and nothing legitimately writes to it, so lock it to
-- read-only rather than denying access outright (a bare ENABLE ROW LEVEL
-- SECURITY with no policy would default to deny-all and could break PostGIS
-- geometry operations, e.g. ST_Transform, that look up SRID definitions
-- under the caller's role).
--
-- CAVEAT: spatial_ref_sys is owned by `supabase_admin`, while `supabase db
-- push` connects as `postgres`, which is not a superuser and does not own
-- this table. This statement WILL fail with "must be owner of table
-- spatial_ref_sys" when run through the normal migration pipeline (locally
-- or on the linked/remote project). It must instead be applied once by
-- connecting directly as `supabase_admin` (e.g. `docker exec <db-container>
-- psql -U supabase_admin -d postgres -f <this file>`), after which mark
-- this version applied so future pushes don't keep retrying it:
-- `supabase migration repair --status applied 20260805000002 [--linked|--local]`.
ALTER TABLE public.spatial_ref_sys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access to spatial reference systems"
    ON public.spatial_ref_sys
    FOR SELECT
    TO anon, authenticated
    USING (true);
