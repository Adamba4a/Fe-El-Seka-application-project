CREATE TABLE IF NOT EXISTS public.admin_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL REFERENCES auth.users(id),
    action_type TEXT NOT NULL
        CHECK (action_type IN ('approved', 'rejected', 'suspended', 'reinstated', 'unlocked')),
    target_user_id UUID NOT NULL REFERENCES public.profiles(id),
    submission_id UUID REFERENCES public.verification_submissions(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.admin_audit_logs ENABLE ROW LEVEL SECURITY;
