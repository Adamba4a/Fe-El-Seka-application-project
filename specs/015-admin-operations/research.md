# Phase 0 Research: Admin Operations (Full)

No `NEEDS CLARIFICATION` markers remain in the Technical Context — the spec's own
`/speckit-clarify` session already resolved the two decisions with product-level implications
(admin-suspension block, export-as-ordinary-download). The items below are the plan-level technical
unknowns identified while grounding the plan in the real `services/api`/`apps/admin` codebase.

## 1. Read pattern for new aggregation endpoints: `asyncpg` vs. `supabase-py`

- **Decision**: Use `asyncpg` raw SQL (via `get_pool()`) for `dashboard_service.py` and
  `financial_report_service.py`. Use the existing `supabase-py` service-role client pattern for the
  search/filter/detail additions to `users_router.py` and `verification_router.py`.
- **Rationale**: The codebase already has both patterns and picks between them based on query shape,
  not team preference — `wallet_service.py` uses `asyncpg` for exactly this kind of ledger
  sum/aggregate query (`SUM`, `GROUP BY`, running balances), while `verification_router.py` and
  `users_router.py` use `supabase-py`'s query builder for simple filtered/paginated list-and-detail
  reads. Dashboard KPIs, trend series, and the financial report are `GROUP BY`/date-bucketed
  aggregates — the same shape `wallet_service.py` already handles — so `asyncpg` is the established
  tool for this shape, not a new choice. User/verification search-and-filter is the same shape the
  existing routers already serve, so extending them with `supabase-py` `.ilike()`/`.eq()` chains keeps
  one pattern per resource instead of introducing a second style into an already-working router.
- **Alternatives considered**: Rewriting `users_router.py`/`verification_router.py` entirely onto
  `asyncpg` for consistency — rejected as unnecessary churn on working, tested endpoints; the
  spec's changes to these routers are additive (new query params, new endpoints), not a rewrite.

## 2. Charting library for dashboard/financial trend series

- **Decision**: `recharts`.
- **Rationale**: `apps/admin/package.json` has no charting dependency today (confirmed by direct
  inspection) — this is a genuinely new choice, not an existing convention to follow. `recharts` is
  the standard pairing for shadcn/ui-based Next.js apps (shadcn/ui ships a `chart` component built
  directly on `recharts`), keeps the bundle lightweight, and needs nothing from the backend beyond
  plain `{date, value}` arrays, which `dashboard_service.get_daily_trend()` and
  `financial_report_service.get_report()` already return.
- **Alternatives considered**: `chart.js`/`react-chartjs-2` (heavier, imperative canvas API, no
  shadcn/ui integration); a hand-rolled SVG sparkline (would work for the simple two-metric dashboard
  trend but not for the financial report's variable daily/weekly series without real engineering
  effort for no benefit over an existing library).

## 3. `profiles` has no `phone_number` column — search field mismatch

- **Decision**: Treat FR-005 and FR-013's "search by ... phone number ..." as search over
  `display_name` and `email` only. No phone column is added.
- **Rationale**: Migration `20260616000001_rename_phone_to_email.sql` renamed
  `profiles.phone_number` to `profiles.email` on 2026-06-16, and a repo-wide search of
  `services/api/app` for `phone` (case-insensitive) returns zero matches — there is no
  reintroduced phone field anywhere in the current backend. The spec's phrasing reflects the
  pre-rename schema description carried over from `003-auth-verification`'s original text. Since the
  rename means "phone number" and "the identifier admins search by" now point at the same physical
  column (`email`), this is a documentation/wording mismatch with zero functional ambiguity, not a
  product decision — it does not warrant a `NEEDS CLARIFICATION` or a re-opened clarification session.
- **Alternatives considered**: Re-adding a `phone_number` column to fulfill the spec text literally —
  rejected; it would require a new migration and new intake UI for a field no other part of the
  platform (auth, notifications) currently uses, entirely to satisfy a stale word choice in a
  requirement whose underlying intent (search by the user's contact identifier) is already met by
  `email`.

## 4. Reference timezone computation (FR-024)

- **Decision**: Compute all "today"/period-preset and financial date-range boundaries server-side in
  `dashboard_service.py`/`financial_report_service.py` using a hardcoded `Africa/Cairo` (`Etc/GMT-2`,
  no DST) reference, via Python's `zoneinfo.ZoneInfo("Africa/Cairo")` — not from the admin's browser
  timezone or a per-request header.
- **Rationale**: FR-024 requires every admin to see identical totals regardless of where they are
  physically located; computing boundaries server-side from a fixed zone is the only way to guarantee
  that. `zoneinfo` is stdlib (Python 3.9+, and this project targets 3.11) — no new dependency.
- **Alternatives considered**: Passing the admin's browser timezone and normalizing per-request —
  rejected, directly contradicts FR-024's "consistent across every screen" requirement.

## 5. CSV export streaming approach (FR-020, NFR-004, NFR-007)

- **Decision**: `financial_report_service.stream_report_csv()` is an async generator yielding CSV rows
  incrementally (using stdlib `csv.writer` against an in-memory `io.StringIO` buffer flushed per
  batch), consumed by a FastAPI `StreamingResponse` with `media_type="text/csv"` and a
  `Content-Disposition: attachment` header. No temp file, no Supabase Storage object, no signed URL.
- **Rationale**: Matches the Clarifications session's "ordinary direct download" resolution and
  NFR-007's explicit prohibition on server-side persistence; streaming rather than building the full
  CSV string in memory first satisfies NFR-004 (large ranges must not block the admin's ability to
  navigate elsewhere) by keeping memory bounded regardless of range size.
- **Alternatives considered**: Building the full CSV in memory and returning it as a single
  `Response` — acceptable at current scale (~100 rides/day) but rejected in favor of the streaming
  generator since it costs nothing extra to implement correctly now and directly satisfies NFR-004's
  large-range wording without a future rewrite.
