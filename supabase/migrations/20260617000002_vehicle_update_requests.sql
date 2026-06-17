CREATE TABLE IF NOT EXISTS public.vehicle_update_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID NOT NULL REFERENCES public.profiles(id),
    vehicle_id UUID NOT NULL REFERENCES public.vehicles(id),
    plate_number TEXT,
    make TEXT,
    model TEXT,
    year INTEGER,
    status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected')),
    rejection_reason TEXT,
    reviewer_id UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.vehicle_update_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "drivers_select_own_vehicle_update_requests"
    ON public.vehicle_update_requests FOR SELECT
    USING (driver_id = auth.uid());

CREATE POLICY "drivers_insert_own_vehicle_update_requests"
    ON public.vehicle_update_requests FOR INSERT
    WITH CHECK (driver_id = auth.uid());
