-- Create private storage buckets
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
    ('profile-photos', 'profile-photos', FALSE, 5242880, ARRAY['image/jpeg', 'image/png']),
    ('identity-documents', 'identity-documents', FALSE, 10485760, ARRAY['image/jpeg', 'image/png'])
ON CONFLICT (id) DO NOTHING;

-- ── profile-photos policies ───────────────────────────────────────────────────
CREATE POLICY "profile_photos_insert_own" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'profile-photos'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );

CREATE POLICY "profile_photos_select_own" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'profile-photos'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );

CREATE POLICY "profile_photos_update_own" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'profile-photos'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );

CREATE POLICY "profile_photos_delete_own" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'profile-photos'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );

-- ── identity-documents policies ───────────────────────────────────────────────
-- Users can upload to their own folder; NO select policy for users.
-- Only service role (backend) generates signed URLs for admin viewing.
CREATE POLICY "identity_docs_insert_own" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'identity-documents'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );
