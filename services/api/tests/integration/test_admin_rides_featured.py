from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.admin import rides_router
from app.dependencies.roles import get_current_admin
from app.main import app
from app.services import audit_service


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeConn:
    def __init__(self, fetchrow_results):
        self._fetchrow_results = list(fetchrow_results)

    async def fetchrow(self, query, *args):
        return self._fetchrow_results.pop(0)


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_admin, None)


@pytest.fixture
def admin_id():
    return uuid4()


@pytest.fixture(autouse=True)
def _override_admin(admin_id):
    app.dependency_overrides[get_current_admin] = lambda: {"id": str(admin_id), "role": "admin"}


@pytest.fixture
def captured_audit_calls(monkeypatch):
    calls = []

    def _fake_append_log(*args, **kwargs):
        calls.append((args, kwargs))
        return str(uuid4())

    monkeypatch.setattr(audit_service, "append_log", _fake_append_log)
    monkeypatch.setattr(rides_router.audit_service, "append_log", _fake_append_log)
    return calls


class TestFeatureRide:
    def test_success(self, client, monkeypatch, admin_id, captured_audit_calls):
        ride_id = uuid4()
        driver_id = uuid4()
        featured_at = datetime.now(timezone.utc)
        conn = _FakeConn([
            {
                "status": "scheduled",
                "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
                "available_seats": 2,
                "driver_id": driver_id,
            },
            {"featured_at": featured_at, "featured_by": admin_id},
        ])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/feature")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ride_id"] == str(ride_id)
        assert body["is_featured"] is True
        assert body["featured_by"] == str(admin_id)

        assert len(captured_audit_calls) == 1
        args, kwargs = captured_audit_calls[0]
        assert args[0] == str(admin_id)
        assert args[1] == "ride_featured"
        assert args[2] == str(driver_id)
        assert kwargs["ride_id"] == str(ride_id)

    def test_not_found(self, client, monkeypatch):
        ride_id = uuid4()
        conn = _FakeConn([None])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/feature")

        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_not_eligible_status(self, client, monkeypatch):
        ride_id = uuid4()
        conn = _FakeConn([
            {
                "status": "completed",
                "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
                "available_seats": 2,
                "driver_id": uuid4(),
            },
        ])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/feature")

        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "not_eligible"
        assert "status must be scheduled" in body["message"]

    def test_not_eligible_departed(self, client, monkeypatch):
        ride_id = uuid4()
        conn = _FakeConn([
            {
                "status": "scheduled",
                "departure_datetime": datetime.now(timezone.utc) - timedelta(hours=1),
                "available_seats": 2,
                "driver_id": uuid4(),
            },
        ])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/feature")

        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "not_eligible"
        assert "departure has already passed" in body["message"]

    def test_not_eligible_no_seats(self, client, monkeypatch):
        ride_id = uuid4()
        conn = _FakeConn([
            {
                "status": "scheduled",
                "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
                "available_seats": 0,
                "driver_id": uuid4(),
            },
        ])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/feature")

        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "not_eligible"
        assert "no seats available" in body["message"]


class TestUnfeatureRide:
    def test_success(self, client, monkeypatch, admin_id, captured_audit_calls):
        ride_id = uuid4()
        driver_id = uuid4()
        featured_at = datetime.now(timezone.utc)
        conn = _FakeConn([
            {"driver_id": driver_id},
            {"featured_at": featured_at, "featured_by": admin_id},
        ])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/unfeature")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ride_id"] == str(ride_id)
        assert body["is_featured"] is False

        assert len(captured_audit_calls) == 1
        args, kwargs = captured_audit_calls[0]
        assert args[1] == "ride_unfeatured"
        assert args[2] == str(driver_id)
        assert kwargs["ride_id"] == str(ride_id)

    def test_not_found(self, client, monkeypatch):
        ride_id = uuid4()
        conn = _FakeConn([None])
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/admin/rides/{ride_id}/unfeature")

        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"
