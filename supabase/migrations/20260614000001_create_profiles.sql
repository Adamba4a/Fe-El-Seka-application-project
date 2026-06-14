-- Extend auth.users with application-specific profile data
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    phone_number TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 2 AND 50),
    role TEXT NOT NULL CHECK (role IN ('passenger', 'driver', 'admin')),
    profile_photo_path TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'pending_review', 'verified', 'rejected', 'suspended')),
    is_submission_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
