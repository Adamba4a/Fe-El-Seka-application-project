# Research: Financial System (Phase 8)

**Branch**: `011-financial-system` | **Date**: 2026-06-29

---

## 1. Financial Decimal Types

**Decision**: `NUMERIC(12, 2)` for all EGP columns in PostgreSQL; `decimal.Decimal` in Python; Pydantic `Decimal` with `max_digits=12, decimal_places=2`.

**Rationale**: Floating-point types (`FLOAT`, `DOUBLE PRECISION`, Python `float`) cannot represent decimal fractions exactly, causing rounding errors in financial arithmetic (e.g., `0.1 + 0.2 ≠ 0.3`). `NUMERIC` is an arbitrary-precision exact type — every stored value is exactly what was written. Python's `decimal.Decimal` with a fixed context prevents accumulation across repeated arithmetic. Pydantic's `Decimal` field type serialises cleanly to/from JSON without float conversion.

**Alternatives considered**:
- `FLOAT` / `float`: Rejected — known rounding hazards; unsuitable for audited financial records.
- Integer cents (multiply by 100, store as `BIGINT`): Valid in principle but conflicts with the existing `fare_amount_egp` and `fuel_cost_egp` patterns already established by Phase 5 and Phase 6 using `NUMERIC`. Mixing representations creates conversion risk.

---

## 2. Pessimistic Row-Level Locking with asyncpg

**Decision**: `SELECT ... FOR UPDATE` on `driver_wallets` during every balance-mutating transaction (commission deduction, reservation creation, admin debit). Use `asyncpg` raw SQL (no ORM).

**Rationale**: The project already uses `asyncpg` raw SQL (confirmed in Phase 7 plan). `SELECT ... FOR UPDATE` acquires a row-level exclusive lock, blocking concurrent transactions from reading (with `FOR UPDATE`) the same wallet row until the first transaction commits. This prevents lost-update anomalies when two rides complete simultaneously or two ride-creation requests race.

The pattern is identical to the `notification_events` dispatcher in Phase 7 which uses `SELECT ... FOR UPDATE SKIP LOCKED` for its queue-consumer behaviour. Phase 8 uses `FOR UPDATE` without `SKIP LOCKED` (block, not skip) — exactly what's needed when the second transaction must see the first's committed result rather than skip it.

**Alternatives considered**:
- Optimistic locking (compare-and-swap on a version column): Requires retry loops in application code; acceptable for low-contention reads but adds complexity when contention is expected during simultaneous ride completions.
- Advisory locks: Database-level named locks; more flexible but harder to reason about scope and release semantics. Row locks tied to the wallet row are simpler.

---

## 3. Append-Only Ledger Enforcement

**Decision**: Two-layer enforcement: (a) database role privilege revocation — `REVOKE UPDATE, DELETE ON driver_ledger_entries FROM app_role`; (b) RLS policy — `USING (driver_id = auth.uid())` for driver reads, no UPDATE/DELETE policies defined for any role.

**Rationale**: API-layer enforcement alone (no `UPDATE`/`DELETE` endpoint) is insufficient — a compromised application process could still issue raw SQL. Revoking `UPDATE` and `DELETE` from the database role that the FastAPI backend uses makes the constraint a database invariant, not a policy. RLS provides the isolation between drivers (each driver sees only their own rows).

Admin ledger reads require a service-role or a separate admin RLS policy that bypasses the driver filter. This matches the existing RLS pattern across Phase 4–7.

**Alternatives considered**:
- Database triggers that raise exceptions on UPDATE/DELETE: Equivalent protection but more brittle (triggers can be disabled by superusers). Privilege revocation is simpler and the standard approach.
- Application-only enforcement: Rejected — insufficient for an audited financial system.

---

## 4. Materialized Balance vs. On-Read Computation

**Decision**: Materialized running total — `driver_wallets.balance_egp` is updated in the same transaction as each ledger INSERT; `driver_wallets.reserved_egp` is updated in the same transaction as each `CommissionReservation` INSERT/DELETE.

**Rationale**: Computing balance on every read (`SELECT SUM(amount_egp) ...`) requires a full ledger scan per request. At MVP scale (≤1,000 drivers, a few hundred entries each) this is acceptable, but the Phase 7 plan already established the materialized pattern for `balance_egp` in the constitution's Technical Standards ("Databases are the source of truth"). Materialisation means every wallet read is a single-row O(1) lookup against `driver_wallets`. The trade-off — every write must update both the ledger and the wallet row atomically — is managed by `SELECT FOR UPDATE`.

SC-006 mandates a periodic integrity check that validates `balance_egp = SUM(credits) - SUM(debits)` and `reserved_egp = SUM(active reservations)`. This check is not a performance concern (run offline or on-demand, not on every request).

**Alternatives considered**:
- Pure append-only with on-read aggregation: Simpler writes, but O(n) reads. Works at MVP scale but harder to enforce consistent balance enforcement atomically (must aggregate inside the transaction under a lock — more complex, same lock requirement).
- Event sourcing with CQRS: Overkill for MVP scale and team size. No existing event bus infrastructure.

---

## 5. Commission Reservation Pattern

**Decision**: Explicit `CommissionReservation` table with a materialized `reserved_egp` counter on `driver_wallets`. The balance check and reservation INSERT are inside the same transaction as the ride INSERT, under `SELECT FOR UPDATE` on `driver_wallets`.

**Rationale**: A "soft hold" pattern — physically recording a reservation and tracking it as a counter — is the standard approach used by banking systems and booking platforms. The alternative (optimistic check at creation, deduction at completion, accepting occasional over-commitment) was explicitly considered and rejected by the user (spec session 2026-06-29, Q5).

The atomicity requirement (check available balance → INSERT reservation → INSERT ride, all-or-nothing) means these three steps must execute in one transaction with the wallet row locked. Any rollback leaves no reservation and no ride. This is the same "check + write in one transaction" pattern used by Phase 7's location upsert.

A single `commission_reservations` table with `ride_id UNIQUE` enforces the "at most one reservation per ride" invariant (FR-023) at the database level.

**Alternatives considered**:
- No reservation (snapshot-only check): Rejected — race condition allows two rides to both pass the check, leading to over-commitment.
- Redis-based hold (external lock): Rejected — adds a new infrastructure dependency (Redis) not in the approved stack; also lacks durability across server restarts.
- PostgreSQL advisory locks keyed on `driver_id`: Advisory locks are session-scoped and don't persist after connection close; complex to manage in a connection pool environment. Row locks on `driver_wallets` are simpler and already needed for the `balance_egp` write.

---

## 6. Cancellation Hook into Existing Ride Cancellation Handlers

**Decision**: Extend the existing `cancel_ride()` in `ride_service.py` and the booking-expiry cancellation path in `booking_service.py` to call `release_reservation(ride_id)` inside their existing transaction.

**Rationale**: Phase 4 (`ride_service.py`) already has a `cancel_ride()` function that sets `rides.status = 'cancelled'`. Phase 6 has booking-expiry logic that can trigger implicit cancellations. Both need to release reservations. Rather than a trigger or event listener (async, which breaks atomicity), the release call is inserted directly into the cancellation transaction — the same tight-coupling pattern used for commission deduction inside `complete_ride()`.

**Alternatives considered**:
- PostgreSQL trigger on `rides.status` change: Automatically releases reservation when status changes to `cancelled`. Attractive for ensuring coverage, but triggers fire after the application transaction, requiring careful ordering. Also harder to test. Inline call is simpler and already aligned with Phase 7's approach for notification events.
- Scheduled cleanup job: Detects orphaned reservations and releases them retroactively. Needed as a safety net (SC-008 orphan check) but not sufficient as the primary release mechanism — it introduces latency and allows a window where available balance is underreported.
