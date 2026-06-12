-- Foundation schema: users, rides, bookings
-- Phase 1: Core identifying fields only.
-- Additional domain fields added per-specification in Phases 3-9.
-- RLS is enabled on all tables with permissive stub policies (replaced in Phase 3+).

-- ─────────────────────────────────────────────────────────────────────────────
-- USERS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       VARCHAR(20) UNIQUE NOT NULL,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('passenger', 'driver', 'both')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_phase1" ON users
    FOR ALL USING (true) WITH CHECK (true);


-- ─────────────────────────────────────────────────────────────────────────────
-- RIDES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE rides (
    id           UUID                   PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id    UUID                   NOT NULL REFERENCES users(id),
    origin       GEOMETRY(POINT, 4326)  NOT NULL,
    destination  GEOMETRY(POINT, 4326)  NOT NULL,
    departure_at TIMESTAMPTZ            NOT NULL,
    status       VARCHAR(20)            NOT NULL DEFAULT 'active'
                                        CHECK (status IN ('active', 'paused', 'cancelled', 'completed')),
    created_at   TIMESTAMPTZ            NOT NULL DEFAULT NOW()
);

-- BTREE indices for relational lookups and time-range filtering
CREATE INDEX rides_driver_id_idx    ON rides (driver_id);
CREATE INDEX rides_departure_at_idx ON rides (departure_at);

-- GIST spatial indices — required for performant PostGIS queries
CREATE INDEX rides_origin_gist_idx ON rides USING GIST (origin);
CREATE INDEX rides_dest_gist_idx   ON rides USING GIST (destination);

ALTER TABLE rides ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_phase1" ON rides
    FOR ALL USING (true) WITH CHECK (true);


-- ─────────────────────────────────────────────────────────────────────────────
-- BOOKINGS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE bookings (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id      UUID        NOT NULL REFERENCES rides(id),
    passenger_id UUID        NOT NULL REFERENCES users(id),
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX bookings_ride_id_idx      ON bookings (ride_id);
CREATE INDEX bookings_passenger_id_idx ON bookings (passenger_id);

ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_phase1" ON bookings
    FOR ALL USING (true) WITH CHECK (true);
