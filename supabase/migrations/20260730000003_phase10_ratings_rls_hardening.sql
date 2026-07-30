-- Phase 10 Trust & Community: NFR-005 hardening.
--
-- The original "rating_party_select" policy let the ratee SELECT raw rows
-- (including unfiltered comment text) directly via the Supabase REST API.
-- That bypasses the double-blind reveal/anonymization logic that
-- rating_service.get_own_rating_summary() enforces at the application layer
-- (a comment is only surfaced once the counterpart has also rated, the ride
-- was never completed, or 14 days have passed). All legitimate reads already
-- go through the backend's service-role connection, which is not subject to
-- RLS, so narrowing this policy to the rater's own submissions only closes
-- the bypass with no functional impact.
DROP POLICY IF EXISTS "rating_party_select" ON public.ratings;

CREATE POLICY "rater_select_own_submissions" ON public.ratings
    FOR SELECT USING (auth.uid() = rater_id);
