-- The verification-time selfie now sets profiles.profile_photo_path directly
-- (it doubles as the user's public avatar) instead of being stored as a
-- separate, verification-only artifact.
ALTER TABLE public.verification_submissions
    DROP COLUMN IF EXISTS selfie_path;
