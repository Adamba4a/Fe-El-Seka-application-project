-- Phase 4 admin review (approve/reject) now enqueues push notifications via
-- notification_events instead of calling fcm_service directly after commit
-- (see wallet_topup_service._enqueue_notification) — these event types were
-- never added to the enum.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'wallet_topup_approved';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'wallet_topup_rejected';
