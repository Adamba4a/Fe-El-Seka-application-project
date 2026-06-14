-- Helper function: is current user an admin?
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'admin'
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── profiles ──────────────────────────────────────────────────────────────────
CREATE POLICY "profiles_select_own" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "profiles_select_admin" ON public.profiles
    FOR SELECT USING (public.is_admin());

-- Users may only update display_name and profile_photo_path on their own row.
-- Restricting to these two columns prevents self-promotion to role='admin'.
CREATE POLICY "profiles_update_own" ON public.profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (
        auth.uid() = id
        AND role = (SELECT role FROM public.profiles WHERE id = auth.uid())
        AND verification_status = (SELECT verification_status FROM public.profiles WHERE id = auth.uid())
        AND is_submission_locked = (SELECT is_submission_locked FROM public.profiles WHERE id = auth.uid())
    );

CREATE POLICY "profiles_update_admin" ON public.profiles
    FOR UPDATE USING (public.is_admin());

CREATE POLICY "profiles_insert_own" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- ── verification_submissions ───────────────────────────────────────────────────
CREATE POLICY "submissions_select_own" ON public.verification_submissions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "submissions_select_admin" ON public.verification_submissions
    FOR SELECT USING (public.is_admin());

CREATE POLICY "submissions_insert_own" ON public.verification_submissions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "submissions_update_admin" ON public.verification_submissions
    FOR UPDATE USING (public.is_admin());

-- ── vehicles ──────────────────────────────────────────────────────────────────
CREATE POLICY "vehicles_select_own" ON public.vehicles
    FOR SELECT USING (auth.uid() = driver_id);

CREATE POLICY "vehicles_select_admin" ON public.vehicles
    FOR SELECT USING (public.is_admin());

CREATE POLICY "vehicles_insert_own" ON public.vehicles
    FOR INSERT WITH CHECK (auth.uid() = driver_id);

CREATE POLICY "vehicles_update_own" ON public.vehicles
    FOR UPDATE USING (auth.uid() = driver_id)
    WITH CHECK (auth.uid() = driver_id);

-- ── admin_audit_logs (append-only) ───────────────────────────────────────────
CREATE POLICY "audit_insert_admin" ON public.admin_audit_logs
    FOR INSERT WITH CHECK (public.is_admin());

CREATE POLICY "audit_select_admin" ON public.admin_audit_logs
    FOR SELECT USING (public.is_admin());

-- No UPDATE or DELETE policies on admin_audit_logs — append-only enforced by omission

-- ── platform_settings ─────────────────────────────────────────────────────────
CREATE POLICY "settings_select_authenticated" ON public.platform_settings
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY "settings_update_admin" ON public.platform_settings
    FOR UPDATE USING (public.is_admin());

CREATE POLICY "settings_insert_admin" ON public.platform_settings
    FOR INSERT WITH CHECK (public.is_admin());
