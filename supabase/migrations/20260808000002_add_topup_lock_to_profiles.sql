-- Phase 15 (interim): Manual Wallet Top-Up via Vodafone Cash
-- Adds the resubmission-cap lock columns for wallet top-up requests (FR-014/FR-015/FR-016).
--
-- Deliberately separate from the existing is_submission_locked column (identity
-- verification, Phase 3): identity-verification and wallet-topup lock cycles are
-- independent, so locking/unlocking one must never affect the other.
--
-- topup_lock_reset_at is the boundary marker for counting REJECTED outcomes toward
-- the 3-strike cap: only REJECTED requests created after this timestamp (or since
-- account creation, if NULL) count. It advances on admin unlock and on any APPROVED
-- outcome (see services/api/app/services/wallet_topup_service.py).

ALTER TABLE public.profiles
    ADD COLUMN is_topup_locked      BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN topup_lock_reset_at  TIMESTAMPTZ;
