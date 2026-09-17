# Quickstart: Ride Preferences and Round Trips

## 1. Private profile gender

1. Create a new driver and passenger profile.
2. Complete onboarding with gender `woman` for the driver and passenger.
3. Confirm `GET /api/profiles/me` includes gender for the authenticated caller.
4. Confirm `GET /api/profiles/{id}` does not include gender.

## 2. Women-only rule

1. As the woman driver, post a one-way ride with `is_women_only: true`.
2. Attempt to post the same option as a man driver; expect `403 women_only_driver_required`.
3. Attempt a booking as a man passenger; expect `403 women_only_ride`, with `booked_seats` unchanged and no booking/wallet rows created.
4. Book as the woman passenger; confirm the normal pending-booking flow succeeds.

## 3. One-off round trip

1. Post a round trip with outbound departure, return departure, and separate outbound/return price and seats.
2. Confirm two linked ride rows exist: outbound has the requested route and return has the reverse route.
3. Book an outbound seat and confirm return availability is unchanged.
4. Book a return seat and confirm outbound availability is unchanged.
5. Reject a return time at or before the outbound time, and an attempted edit that reverses their ordering.

## 4. Recurring round trip and one-date override

1. Create a recurring round-trip definition for Monday and Wednesday with outbound and return times, seats, and prices.
2. Run generation and confirm each selected date gets exactly one linked outbound/return pair.
3. Override one date's two times; confirm both rows change together and a later date keeps the definition's standard times.
4. Add a booking to either leg, retry the override, and confirm neither leg changes.

