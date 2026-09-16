# Capacity testing and scaling

## What is measured
The API exposes a per-worker rolling 15-minute summary at `GET /api/internal/metrics`. Send `X-Internal-Secret` with the existing `INTERNAL_SECRET` value. The summary includes p50/p95 request duration, 4xx/5xx counts, inflight requests, route-group summaries, and asyncpg pool occupancy. It deliberately excludes query strings, request data, user identifiers and dynamic route identifiers.

This is per process/pod, not a global metric store. With the current two Uvicorn workers, query each worker/pod if you need a complete total after replicas are added.

## Staged load test

Install k6 using its official installation method. Create dedicated staging passenger test accounts that are organization-verified and have no production data you care about. The script only sends health and authenticated GET requests. It does not create or modify rides, bookings, locations, wallet balances, profiles, support reports, or admin data.

```powershell
$env:BASE_URL = "https://staging-api.example.com"
$env:TEST_PASSENGER_TOKEN = "token for a dedicated test passenger"
$env:ALLOW_PRODUCTION = "true" # required for any non-local target
k6 run performance/k6/capacity.js
```

Start at 10/25/50 virtual users. Increase `PEAK_VUS` only after the previous run meets all thresholds: p95 under 500 ms, failed requests below 1%, no sustained 5xx errors, and database idle connections remain available.

Never run this against production until you have an approved test window. If production testing is approved, use an isolated test account and a low initial peak (10 VUs), watch Bunny and Supabase dashboards continuously, and stop on the first threshold breach.

## Scaling order

1. Identify the bottleneck using p95 by route and database pool occupancy. A full pool means requests are waiting for Supabase; slow search routes can instead indicate OSRM or AI.
2. Increase API memory/CPU in Bunny first. The current API has two workers and a pool of ten database connections per worker, so one API instance can hold up to 20 database connections.
3. Add API replicas only when the database has connection and CPU headroom. Two replicas can hold up to 40 API database connections; update Supabase pooling capacity before or together with this step.
4. Scale OSRM for route-heavy searches and AI independently for scoring-heavy searches. Do not increase all services together without measurements.
5. Keep static Next.js traffic at the edge/CDN and move expensive non-user-facing work to durable background queues before raising API replicas further.

## Current capacity decision rule

The earlier 50–100 simultaneous-active-user figure is a conservative launch hypothesis, not an established limit. It becomes a measured limit only after a successful staged run using real production-sized data and the thresholds above.
