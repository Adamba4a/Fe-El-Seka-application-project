-- Ensure booking_reminder exists in the notification_event_type enum.
-- This guards against the case where the Phase 7 migration was recorded in
-- schema_migrations but the ALTER TYPE statement did not execute.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'booking_reminder';
