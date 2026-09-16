CREATE TABLE public.support_requests (
    id uuid PRIMARY KEY,
    email text NOT NULL CHECK (length(email) BETWEEN 3 AND 254),
    description text NOT NULL CHECK (length(btrim(description)) BETWEEN 10 AND 5000),
    locale text NOT NULL CHECK (locale IN ('en', 'ar')),
    client_fingerprint text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
    email_status text NOT NULL DEFAULT 'pending' CHECK (email_status IN ('pending', 'sent', 'failed')),
    email_attempts integer NOT NULL DEFAULT 0,
    next_email_attempt_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX support_requests_created ON public.support_requests (created_at DESC);
CREATE INDEX support_requests_email_rate ON public.support_requests (email, created_at);
CREATE INDEX support_requests_client_rate ON public.support_requests (client_fingerprint, created_at);
CREATE INDEX support_requests_delivery ON public.support_requests (next_email_attempt_at) WHERE email_status = 'pending';

CREATE TABLE public.support_status_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES public.support_requests(id),
    admin_id uuid NOT NULL REFERENCES public.profiles(id),
    old_status text NOT NULL,
    new_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.support_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_status_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.support_requests, public.support_status_history FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.support_requests TO service_role;
GRANT SELECT, INSERT ON public.support_status_history TO service_role;
