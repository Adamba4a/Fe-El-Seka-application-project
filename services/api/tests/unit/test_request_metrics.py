from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal.metrics_router import router
from app.core.config import settings
from app.core.request_metrics import RequestMetrics, normalize_path


def test_normalizes_dynamic_and_unknown_paths():
    assert normalize_path("/api/v1/rides/2b4d9db0-713d-4d7f-8ff1-4c0bfc2d11f7") == "/api/v1/rides/{id}"
    assert normalize_path("/api/admin/users/124") == "/api/admin/users/{id}"
    assert normalize_path("/not-an-api-path/private@example.com") == "/other"
    assert normalize_path("/api/v1/rides/private@example.com") == "/api/v1/rides/{path}"


def test_snapshot_is_bounded_and_reports_percentiles():
    now = [1_000.0]
    metrics = RequestMetrics(now=lambda: now[0])
    metrics.begin()
    metrics.record("/api/v1/rides/2b4d9db0-713d-4d7f-8ff1-4c0bfc2d11f7", "GET", 200, 10)
    metrics.begin()
    metrics.record("/api/v1/rides/2b4d9db0-713d-4d7f-8ff1-4c0bfc2d11f7", "GET", 503, 100)
    metrics.begin()
    metrics.record("/not-an-api-path/person@example.com", "GET", 404, 20)
    snapshot = metrics.snapshot()
    assert snapshot["request_count"] == 3
    assert snapshot["p50_ms"] == 20
    assert snapshot["p95_ms"] == 100
    assert snapshot["errors_5xx"] == 1
    assert snapshot["errors_4xx"] == 1
    assert snapshot["slowest_endpoints"][0]["path"] == "/api/v1/rides/{id}"
    assert "person@example.com" not in str(snapshot)
    now[0] += 901
    assert metrics.snapshot()["request_count"] == 0


def test_snapshot_reports_pool_state():
    class Pool:
        def get_size(self):
            return 4

        def get_idle_size(self):
            return 2

        def get_max_size(self):
            return 10

    assert RequestMetrics().snapshot(Pool())["database"] == {
        "connections_open": 4,
        "connections_idle": 2,
        "connections_max": 10,
    }


def test_metrics_endpoint_requires_existing_internal_secret(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api/internal")
    monkeypatch.setattr(settings, "internal_secret", "test-internal-secret")
    client = TestClient(app)
    assert client.get("/api/internal/metrics").status_code == 403
    assert client.get("/api/internal/metrics", headers={"X-Internal-Secret": "wrong"}).status_code == 403
    response = client.get("/api/internal/metrics", headers={"X-Internal-Secret": "test-internal-secret"})
    assert response.status_code == 200
    assert "request_count" in response.json()
