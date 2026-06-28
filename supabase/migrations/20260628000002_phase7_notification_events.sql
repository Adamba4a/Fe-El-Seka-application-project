-- Phase 7: Real-Time Transportation — FCM push notification dispatch queue
-- Creates: notification_event_type enum, notification_event_status enum,
--          notification_events table
-- NOTE: This is separate from email_notifications (Phase 6). FCM push only.

CREATE TYPE notification_event_type AS ENUM (
    'booking_received',
    'booking_confirmed',
    'booking_rejected',
    'booking_cancelled',
    'booking_expired',
    'ride_cancelled',
    'ride_started',
    'ride_completed'
);

CREATE TYPE notification_event_status AS ENUM (
    'pending',
    'dispatched',
    'failed'
);

CREATE TABLE public.notification_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    event_type        notification_event_type NOT NULL,
    payload           JSONB NOT NULL DEFAULT '{}',
    status            notification_event_status NOT NULL DEFAULT 'pending',
    retry_count       SMALLINT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at     TIMESTAMPTZ
);

-- Dispatcher polling: pending rows in insertion order
CREATE INDEX idx_notification_events_pending
    ON public.notification_events (created_at ASC)
    WHERE status = 'pending';

ALTER TABLE public.notification_events ENABLE ROW LEVEL SECURITY;

-- Recipients can read their own notification events (e.g. for in-app inbox)
CREATE POLICY "user_read_own_events" ON public.notification_events
    FOR SELECT USING (recipient_user_id = auth.uid());

-- No client INSERT/UPDATE: backend service role only
