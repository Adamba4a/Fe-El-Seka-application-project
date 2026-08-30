-- Spec 026: withdrawal_service._enqueue_notification (T018) enqueues push
-- notifications via notification_events on approve/reject — these event
-- types were never added to the enum. Mirrors
-- 20260814000004_wallet_topup_notification_types.sql for the reverse flow.
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'withdrawal_approved';
ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS 'withdrawal_rejected';
