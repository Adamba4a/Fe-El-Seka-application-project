-- Phase 14 (Arabic & RTL localization): per-user display language preference.
-- NULL means no explicit choice has been made yet, which is the trigger
-- condition for the one-time rollout prompt shown to existing users (FR-013).
ALTER TABLE public.profiles
    ADD COLUMN language_preference TEXT
        CHECK (language_preference IN ('en', 'ar'));
