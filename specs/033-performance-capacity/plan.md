# Implementation Plan: Performance Capacity

FastAPI middleware records an aggregate event after each request. `RequestMetrics` holds a bounded deque guarded by a thread lock and creates a snapshot on demand. The existing internal-secret pattern protects a new endpoint under `/api/internal`.

The k6 scenario is a separate operational tool. It starts at low virtual-user counts and uses only health plus authenticated read/search endpoints. It requires an explicit production opt-in and bearer token, so it cannot accidentally create rides, bookings, support requests, or financial records.

The initial production configuration remains unchanged: two API workers, ten database connections each, and one current container deployment. Metrics are per worker/pod, so an external scraper must query every replica if Bunny scaling introduces more pods.

Constitution check: shared, backend-owned operational capability; no transportation behavior changes; sensitive data is excluded; no violations.
