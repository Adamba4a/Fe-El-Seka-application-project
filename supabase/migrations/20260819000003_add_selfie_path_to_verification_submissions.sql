ALTER TABLE public.verification_submissions
    ADD COLUMN IF NOT EXISTS selfie_path TEXT;
