-- Featured Rides (spec 022): let admin feature/unfeature actions be
-- attributed to a specific ride in the audit trail, alongside the existing
-- target_user_id (the ride's driver).

ALTER TABLE public.admin_audit_logs
    ADD COLUMN ride_id UUID REFERENCES public.rides(id);

ALTER TABLE public.admin_audit_logs
    DROP CONSTRAINT admin_audit_logs_action_type_check;

ALTER TABLE public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_action_type_check
        CHECK (action_type IN (
            'approved', 'rejected', 'suspended', 'reinstated', 'unlocked',
            'ride_featured', 'ride_unfeatured'
        ));
