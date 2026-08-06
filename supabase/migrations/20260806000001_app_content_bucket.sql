-- Public bucket serving runtime-loaded content, starting with the
-- per-locale message catalogs read by apps/main/src/lib/i18n/messages-loader.ts
-- (NFR-003 / specs/017-arabic-rtl-localization/research.md R3: publishing an
-- updated catalog here takes effect on the loader's next refresh, no redeploy).
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('app-content', 'app-content', TRUE, 1048576, ARRAY['application/json'])
ON CONFLICT (id) DO NOTHING;

-- Public bucket already exposes reads via the /storage/v1/object/public/ endpoint
-- with no policy needed; writes are restricted to admins publishing new content.
CREATE POLICY "app_content_admin_write" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'app-content' AND is_admin()
    );

CREATE POLICY "app_content_admin_update" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'app-content' AND is_admin()
    );
