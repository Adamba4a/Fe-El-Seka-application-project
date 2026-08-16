-- Multi-seat bookings: a passenger may reserve more than one seat per ride,
-- and may add more seats to an existing pending/confirmed booking later.
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS seats INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_bookings_seats_positive'
  ) THEN
    ALTER TABLE public.bookings ADD CONSTRAINT chk_bookings_seats_positive
        CHECK (seats > 0);
  END IF;
END $$;

-- New audit-log event type for seat-count increases on an existing booking.
ALTER TYPE booking_event_type ADD VALUE IF NOT EXISTS 'seats_added';

-- New FCM notification event type for the driver-facing "seats added" alert.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'booking_seats_added';
