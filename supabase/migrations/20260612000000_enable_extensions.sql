-- Enable PostGIS for geospatial capabilities (required for GEOMETRY columns).
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable uuid-ossp as a compatibility fallback.
-- gen_random_uuid() is native in PostgreSQL 13+ and preferred for new code.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
