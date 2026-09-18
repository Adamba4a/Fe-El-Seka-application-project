-- Allow the audited manual exception to the organization-email access gate.
ALTER TABLE public.admin_audit_logs
    DROP CONSTRAINT IF EXISTS admin_audit_logs_action_type_check;

ALTER TABLE public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_action_type_check
        CHECK (action_type IN (
            'approved', 'rejected', 'suspended', 'reinstated', 'unlocked', 'warned',
            'ride_featured', 'ride_unfeatured', 'org_access_granted'
        ));
