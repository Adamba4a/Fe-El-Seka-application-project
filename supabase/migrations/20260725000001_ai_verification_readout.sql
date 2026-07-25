-- AI verification triage read-out columns (advisory-only).
--
-- Context: services/ai now runs OCR + face-match + image-quality checks
-- against submitted ID/selfie photos and returns a read-out for the human
-- admin reviewer. Real-corpus calibration (2026-07-25, 6 identities) showed
-- both OCR and face-match have too much genuine/impostor overlap to safely
-- auto-approve/auto-reject, so this is advisory-only: no decision column,
-- no thresholds, no shadow-mode flag. Every submission still routes through
-- the existing pending_review -> admin approve/reject flow unchanged; these
-- columns are purely a hint surfaced next to the existing document viewer.
--
-- All columns nullable: populated only when the AI service was reachable
-- and returned a result; NULL means "no AI read-out available" (AI down,
-- or submission predates this migration), not "AI checked and found nothing".

ALTER TABLE public.verification_submissions
    ADD COLUMN IF NOT EXISTS ai_ocr_text_front TEXT,
    ADD COLUMN IF NOT EXISTS ai_ocr_text_back TEXT,
    ADD COLUMN IF NOT EXISTS ai_name_match_score DOUBLE PRECISION
        CHECK (ai_name_match_score IS NULL OR ai_name_match_score BETWEEN 0 AND 1),
    ADD COLUMN IF NOT EXISTS ai_face_match_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS ai_id_face_detected BOOLEAN,
    ADD COLUMN IF NOT EXISTS ai_selfie_face_detected BOOLEAN,
    ADD COLUMN IF NOT EXISTS ai_image_quality JSONB,
    ADD COLUMN IF NOT EXISTS ai_reasons JSONB,
    ADD COLUMN IF NOT EXISTS ai_model_version TEXT,
    ADD COLUMN IF NOT EXISTS ai_processed_at TIMESTAMPTZ;

-- No RLS policy changes needed: RLS in this schema is row-level, and the
-- existing submissions_select_own/submissions_select_admin/
-- submissions_update_admin policies (20260614000006_rls_policies.sql)
-- already cover all columns on this table, including these new ones.
