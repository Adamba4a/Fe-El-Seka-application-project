-- Verification approve/reject now enqueues push notifications via
-- notification_events (see wallet_topup_service._enqueue_notification /
-- admin/verification_router.py's approve_submission and reject_submission).
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'verification_approved';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'verification_rejected';
