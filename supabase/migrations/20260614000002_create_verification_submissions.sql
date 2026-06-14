CREATE TABLE IF NOT EXISTS public.verification_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id),
    submission_type TEXT NOT NULL CHECK (submission_type IN ('passenger_id', 'driver_id_license')),
    front_id_path TEXT NOT NULL,
    back_id_path TEXT NOT NULL,
    license_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected')),
    rejection_reason TEXT,
    reviewer_id UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number BETWEEN 1 AND 3),
    is_locked BOOLEAN NOT NULL DEFAULT FALSE
);

ALTER TABLE public.verification_submissions ENABLE ROW LEVEL SECURITY;
