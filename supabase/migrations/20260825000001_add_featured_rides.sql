-- Featured Rides (spec 022): let admins curate rides that surface to
-- passengers as recommended. Visibility is computed at read time from
-- these columns plus the ride's existing status/departure/seats — no
-- separate cleanup job clears is_featured when a ride stops being bookable.

ALTER TABLE public.rides
    ADD COLUMN is_featured boolean NOT NULL DEFAULT false,
    ADD COLUMN featured_at timestamptz NULL,
    ADD COLUMN featured_by uuid NULL REFERENCES public.profiles(id);

CREATE INDEX idx_rides_featured_upcoming
    ON public.rides (departure_datetime)
    WHERE is_featured = true AND status = 'scheduled';
