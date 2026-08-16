-- Fix: uq_topup_reference_active enforced uniqueness on the raw payment_reference
-- string. Two submissions of the "same" Vodafone Cash reference that differ only
-- in case or surrounding whitespace (e.g. "TXN123456" vs " txn123456 ") were
-- treated as distinct, letting FR-005's duplicate-reference guard be bypassed
-- trivially. Rebuild the partial unique index on the normalized form so the
-- DB-level guarantee (NFR-005) actually matches the intent: one active request
-- per real-world reference, regardless of case/whitespace.

DROP INDEX IF EXISTS uq_topup_reference_active;

CREATE UNIQUE INDEX uq_topup_reference_active
    ON public.wallet_topup_requests (lower(trim(payment_reference)))
    WHERE status IN ('PENDING', 'APPROVED');
