-- Phase 15 (interim): Manual Wallet Top-Up via Vodafone Cash
-- Creates the private Storage bucket for top-up proof-of-payment screenshots
-- (NFR-002), mirroring the identity-documents bucket pattern exactly: object
-- path convention {driver_id}/{request_id}.{ext}, drivers can upload to their
-- own folder only, no client SELECT policy — only the backend's service-role
-- connection generates signed URLs for admin viewing.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('topup-proofs', 'topup-proofs', FALSE, 10485760, ARRAY['image/jpeg', 'image/png'])
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "topup_proofs_insert_own" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'topup-proofs'
        AND (auth.uid())::TEXT = (storage.foldername(name))[1]
    );
