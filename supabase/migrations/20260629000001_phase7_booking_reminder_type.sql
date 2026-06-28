-- Add booking_reminder to the notification event type enum.
-- This is a distinct event from booking_received (the initial notification).
-- The reminder fires only for pending bookings older than 2 hours that have
-- not yet received a reminder, so NOT EXISTS checks for 'booking_reminder'
-- rather than 'booking_received' to avoid a false deadlock.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'booking_reminder';
