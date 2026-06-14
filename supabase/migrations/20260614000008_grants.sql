-- Explicit table-level grants for PostgREST roles.
-- Supabase local dev should set these via ALTER DEFAULT PRIVILEGES in its init
-- scripts, but they are stated explicitly here to ensure they are always present.
-- Without these, supabase-py (and @supabase/ssr) get "permission denied" (42501)
-- before RLS policies are even evaluated.

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

GRANT ALL ON TABLE public.profiles TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.verification_submissions TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.vehicles TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.admin_audit_logs TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.platform_settings TO anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.is_admin() TO anon, authenticated, service_role;

-- Ensure future tables created in this schema also inherit the grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;
