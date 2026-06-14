CREATE TABLE IF NOT EXISTS public.platform_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

-- Seed default support email
INSERT INTO public.platform_settings (key, value)
VALUES ('support_email', 'support@felseka.com')
ON CONFLICT (key) DO NOTHING;
