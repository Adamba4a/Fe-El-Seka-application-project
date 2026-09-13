-- Ride Auto-Completion Timeout (spec 031)
-- Mirrors the existing rides.cancellation_source column/constraint pattern
-- so a completed ride's source (driver tap vs. automatic timeout sweep) is
-- traceable after the fact. Nullable: existing completed rides predate this
-- column and non-completed rides never get a value.

ALTER TABLE rides ADD COLUMN completion_source TEXT
  CHECK (completion_source = ANY (ARRAY['driver'::text, 'system'::text]));
