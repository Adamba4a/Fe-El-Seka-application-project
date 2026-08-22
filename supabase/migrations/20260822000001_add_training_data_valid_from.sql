-- Excludes known test-account activity from the continuous-learning dataset
-- pipeline (dataset_pipeline_service.py) without needing a separate boolean
-- flag. NULL = fully eligible (default for real users). A finite timestamp
-- means "only match_events from this account at/after this time count" (for
-- an account with a mix of early test rides and later real usage). 'infinity'
-- means "never eligible" (a pure test/QA account).
ALTER TABLE public.profiles
    ADD COLUMN training_data_valid_from TIMESTAMPTZ NULL;

COMMENT ON COLUMN public.profiles.training_data_valid_from IS
    'Dataset pipeline eligibility cutoff. NULL = no restriction. A timestamp excludes match_events before it for this user (either side of the match). Use ''infinity'' for accounts that are pure test/QA and should never contribute training data.';

-- Pure test/QA accounts used to exercise the app before real launch traffic —
-- never eligible for training data.
UPDATE public.profiles
SET training_data_valid_from = 'infinity'
WHERE email IN (
    'triplyy.info@gmail.com',
    'ahmedesaaa35@gmail.com',
    'boudyeid654@gmail.com',
    'ahmednasse061@gmail.com',
    'whiteadam006@gmail.com',
    'yellowadam006@gmail.com',
    'abdelrahman.eid06@eng-st.cu.edu.eg',
    'newcosmics@gmail.com'
);

-- darkadam006@gmail.com has early test rides but will become a real active
-- account whose future activity should count — exclude only its history up
-- to now, not the account permanently.
UPDATE public.profiles
SET training_data_valid_from = NOW()
WHERE email = 'darkadam006@gmail.com';
