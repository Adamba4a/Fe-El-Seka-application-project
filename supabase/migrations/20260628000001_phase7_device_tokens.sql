-- Phase 7: Real-Time Transportation — FCM device token registry
-- Creates: user_device_tokens table with upsert-friendly UNIQUE (token) constraint

CREATE TABLE public.user_device_tokens (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    token         TEXT NOT NULL,
    platform      TEXT NOT NULL CHECK (platform IN ('web', 'android', 'ios')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_device_token UNIQUE (token)
);

-- Dispatcher lookup: all tokens for a given recipient user
CREATE INDEX idx_device_tokens_user_id
    ON public.user_device_tokens (user_id);

ALTER TABLE public.user_device_tokens ENABLE ROW LEVEL SECURITY;

-- Users manage their own tokens; service role has unrestricted access for dispatcher reads
CREATE POLICY "user_manage_own_tokens" ON public.user_device_tokens
    FOR ALL USING (user_id = auth.uid());
