-- Phase 13 (016-continuous-learning-pipeline): training-datasets Storage bucket
-- Mirrors the existing model-registry bucket: private, service-role/asyncpg-only
-- access via the AI service's Supabase client (no end-user upload/download), so
-- no storage.objects policies are added — service role bypasses RLS by default.
-- See specs/016-continuous-learning-pipeline/research.md R8.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('training-datasets', 'training-datasets', FALSE, 104857600, NULL)
ON CONFLICT (id) DO NOTHING;
