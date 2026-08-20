-- car_maintenance_rewards.driver_id / fulfilled_by were mistakenly pointed at
-- the legacy phase-1 `users` table (superseded by `profiles`, effectively
-- empty) instead of `profiles`. Every INSERT into this table failed its FK
-- constraint, which breaks ride completion for any driver who crosses the
-- 3000 EGP car-maintenance-savings threshold — see
-- car_maintenance_service.py's accumulate_and_maybe_grant(), which runs this
-- INSERT inside the same transaction as the commission deduction, so the FK
-- violation rolled back the whole ride-completion request.

ALTER TABLE public.car_maintenance_rewards
    DROP CONSTRAINT car_maintenance_rewards_driver_id_fkey,
    DROP CONSTRAINT car_maintenance_rewards_fulfilled_by_fkey;

ALTER TABLE public.car_maintenance_rewards
    ADD CONSTRAINT car_maintenance_rewards_driver_id_fkey
        FOREIGN KEY (driver_id) REFERENCES public.profiles(id) ON DELETE CASCADE,
    ADD CONSTRAINT car_maintenance_rewards_fulfilled_by_fkey
        FOREIGN KEY (fulfilled_by) REFERENCES public.profiles(id);
