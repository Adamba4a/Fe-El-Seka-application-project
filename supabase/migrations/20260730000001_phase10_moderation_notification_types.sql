-- Phase 10 Trust & Community: moderation outcome notifications, plus the
-- pre-existing 'rating_prompt' event type used by booking_service.py that
-- was never added to the enum.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'moderation_outcome';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'moderation_reinstated';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'rating_prompt';
