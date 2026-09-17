-- Spec 035: private profile gender, women-only rides, and linked round-trip legs.
CREATE TYPE public.profile_gender AS ENUM ('woman', 'man');
CREATE TYPE public.ride_trip_leg AS ENUM ('one_way', 'outbound', 'return');
CREATE TYPE public.recurring_journey_type AS ENUM ('one_way', 'round_trip');

ALTER TABLE public.profiles ADD COLUMN gender public.profile_gender NULL;

ALTER TABLE public.rides
  ADD COLUMN is_women_only boolean NOT NULL DEFAULT false,
  ADD COLUMN round_trip_group_id uuid NULL,
  ADD COLUMN trip_leg public.ride_trip_leg NOT NULL DEFAULT 'one_way',
  ADD CONSTRAINT chk_rides_trip_pairing CHECK (
    (trip_leg = 'one_way' AND round_trip_group_id IS NULL) OR
    (trip_leg IN ('outbound', 'return') AND round_trip_group_id IS NOT NULL)
  );
CREATE UNIQUE INDEX uq_rides_round_trip_leg
  ON public.rides(round_trip_group_id, trip_leg) WHERE round_trip_group_id IS NOT NULL;

ALTER TABLE public.recurring_ride_definitions
  ADD COLUMN journey_type public.recurring_journey_type NOT NULL DEFAULT 'one_way',
  ADD COLUMN is_women_only boolean NOT NULL DEFAULT false,
  ADD COLUMN return_departure_time time NULL,
  ADD COLUMN return_total_seats smallint NULL,
  ADD COLUMN return_price_per_seat numeric(10,2) NULL,
  ADD CONSTRAINT chk_recurring_round_trip_fields CHECK (
    (journey_type = 'one_way' AND return_departure_time IS NULL AND return_total_seats IS NULL AND return_price_per_seat IS NULL) OR
    (journey_type = 'round_trip' AND return_departure_time IS NOT NULL AND return_total_seats >= 1 AND return_price_per_seat > 0)
  );

DROP INDEX IF EXISTS public.uq_rides_recurring_instance_per_date;
CREATE UNIQUE INDEX uq_rides_recurring_instance_per_date_leg
  ON public.rides (recurring_ride_definition_id, public.utc_date(departure_datetime), trip_leg)
  WHERE recurring_ride_definition_id IS NOT NULL;
