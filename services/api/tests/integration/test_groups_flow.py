from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.services import group_service


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeTransactionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


class _RoutedFakeConn:
    """Routes fetchval/fetchrow/fetch/execute by matching an ordered list of
    (substring, response) rules against the query text — same convention as
    tests/unit/test_group_service.py and tests/integration/test_rides_fare_override.py."""

    def __init__(self, fetchval_rules=None, fetchrow_rules=None, fetch_rules=None, execute_rules=None):
        self._fetchval_rules = fetchval_rules or []
        self._fetchrow_rules = fetchrow_rules or []
        self._fetch_rules = fetch_rules or []
        self._execute_rules = execute_rules or []
        self.executed_queries: list[str] = []

    def _resolve(self, rules, query, default=...):
        for substring, response in rules:
            if substring in query:
                return response() if callable(response) else response
        if default is not ...:
            return default
        raise AssertionError(f"Unmatched query: {query}")

    async def fetchval(self, query, *args):
        return self._resolve(self._fetchval_rules, query)

    async def fetchrow(self, query, *args):
        return self._resolve(self._fetchrow_rules, query)

    async def fetch(self, query, *args):
        return self._resolve(self._fetch_rules, query, default=[])

    async def execute(self, query, *args):
        self.executed_queries.append(query)
        return self._resolve(self._execute_rules, query, default="OK")

    def transaction(self):
        return _FakeTransactionCtx()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _group_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "name": "El Shorouk Commuters",
        "type": "general",
        "description": "Daily corridor carpool",
        "route_tags": ["el-shorouk", "cairo"],
        "member_count": 1,
    }
    row.update(overrides)
    return row


class TestCreateAndSearchGroup:
    def test_create_group_returns_201_summary(self, client, monkeypatch):
        user_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(user_id),
            "org_verified_at": "2026-01-01T00:00:00+00:00",
        }
        row = _group_row()
        conn = _RoutedFakeConn(fetchrow_rules=[("INSERT INTO groups", row)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(
            "/api/groups",
            json={
                "name": "El Shorouk Commuters",
                "description": "Daily corridor carpool",
                "route_tags": ["el-shorouk", "cairo"],
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == str(row["id"])
        assert body["member_count"] == 1

    def test_create_group_requires_org_verified_email(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(uuid.uuid4()),
            "org_verified_at": None,
        }

        resp = client.post("/api/groups", json={"name": "Test", "route_tags": []})

        assert resp.status_code == 403
        assert resp.json()["error"] == "org_verification_required"

    def test_search_groups_returns_matches(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid.uuid4())}
        row = _group_row()
        conn = _RoutedFakeConn(
            fetch_rules=[("FROM groups", [row])],
            fetchval_rules=[("COUNT(*)", 1)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.get("/api/groups", params={"q": "shorouk"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "El Shorouk Commuters"


class TestJoinGroup:
    def test_join_general_group_succeeds(self, client, monkeypatch):
        user_id = uuid.uuid4()
        group_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(user_id),
            "org_verified_at": "2026-01-01T00:00:00+00:00",
        }
        membership_row = {
            "id": uuid.uuid4(),
            "group_id": group_id,
            "user_id": user_id,
            "role": "member",
            "joined_at": datetime.now(timezone.utc),
        }
        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("SELECT id, type FROM groups", {"id": group_id, "type": "general"}),
                ("SELECT id, group_id, user_id, role, joined_at\n            FROM group_memberships", None),
                ("INSERT INTO group_memberships", membership_row),
            ],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/groups/{group_id}/join")

        assert resp.status_code == 200
        assert resp.json()["role"] == "member"

    def test_join_nonexistent_group_returns_404(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(uuid.uuid4()),
            "org_verified_at": "2026-01-01T00:00:00+00:00",
        }
        conn = _RoutedFakeConn(fetchrow_rules=[("SELECT id, type FROM groups", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/groups/{uuid.uuid4()}/join")

        assert resp.status_code == 404
        assert resp.json()["error"] == "group_not_found"


class TestMembershipHousekeepingEndpoints:
    def test_list_members_returns_200(self, client, monkeypatch):
        user_id = uuid.uuid4()
        group_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {"id": str(user_id)}
        member_row = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "display_name": "Sara",
            "role": "owner",
            "joined_at": datetime.now(timezone.utc),
        }
        conn = _RoutedFakeConn(
            fetchval_rules=[("FROM groups WHERE id", 1), ("FROM group_memberships", 1)],
            fetch_rules=[("JOIN profiles", [member_row])],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.get(f"/api/groups/{group_id}/members")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["display_name"] == "Sara"

    def test_leave_group_returns_204(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid.uuid4())}
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM group_memberships", {"role": "member"})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/groups/{uuid.uuid4()}/leave")

        assert resp.status_code == 204

    def test_owner_leave_blocked_returns_409(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid.uuid4())}
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM group_memberships", {"role": "owner"})],
            fetchval_rules=[("user_id != $2", 1)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(f"/api/groups/{uuid.uuid4()}/leave")

        assert resp.status_code == 409
        assert resp.json()["error"] == "ownership_transfer_required"

    def test_remove_member_returns_204(self, client, monkeypatch):
        owner_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {"id": str(owner_id)}
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": owner_id})],
            execute_rules=[("DELETE FROM group_memberships", "DELETE 1")],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.delete(f"/api/groups/{uuid.uuid4()}/members/{uuid.uuid4()}")

        assert resp.status_code == 204

    def test_non_owner_remove_returns_403(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid.uuid4())}
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": uuid.uuid4()})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.delete(f"/api/groups/{uuid.uuid4()}/members/{uuid.uuid4()}")

        assert resp.status_code == 403
        assert resp.json()["error"] == "not_group_owner"

    def test_transfer_ownership_returns_200_summary(self, client, monkeypatch):
        owner_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {"id": str(owner_id)}
        summary_row = _group_row()
        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("FROM groups", {"owner_id": owner_id}),
                ("UPDATE groups SET owner_id", summary_row),
            ],
            fetchval_rules=[("FROM group_memberships", 1)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.post(
            f"/api/groups/{uuid.uuid4()}/transfer-ownership",
            json={"new_owner_user_id": str(new_owner_id)},
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(summary_row["id"])

    def test_archive_group_returns_204(self, client, monkeypatch):
        owner_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: {"id": str(owner_id)}
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": owner_id})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        resp = client.delete(f"/api/groups/{uuid.uuid4()}")

        assert resp.status_code == 204

    async def test_archived_group_blocks_new_ride_posting(self, monkeypatch):
        # Closes the FR-021 gap fixed in ride_service.create_ride(): an archived
        # group must reject new ride postings scoped to it. Calls the service
        # directly (not via TestClient) since ride creation takes precomputed
        # pricing/route kwargs the router assembles upstream — same convention
        # as tests/integration/test_rides_fare_override.py.
        from datetime import timedelta

        from app.models.ride import CreateRideRequest, LocationSchema
        from app.services import ride_service

        driver_id = uuid.uuid4()
        group_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("SELECT id FROM rides", None),
                (
                    "JOIN groups g ON g.id = gm.group_id",
                    {"archived_at": datetime.now(timezone.utc)},
                ),
            ],
        )
        monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(conn))

        payload = CreateRideRequest(
            origin=LocationSchema(coordinates={"lat": 30.0131, "lng": 31.2089}, address="A"),
            destination=LocationSchema(coordinates={"lat": 30.0626, "lng": 31.3462}, address="B"),
            departure_datetime=datetime.now(timezone.utc) + timedelta(hours=3),
            total_seats=2,
            group_id=group_id,
        )

        with pytest.raises(ride_service.RideServiceError) as exc_info:
            await ride_service.create_ride(
                driver_id=driver_id,
                vehicle_id=uuid.uuid4(),
                vehicle_seat_count=4,
                payload=payload,
                route_geometry_geojson={"type": "LineString", "coordinates": []},
                route_distance_km=10.0,
                route_duration_minutes=20,
                fuel_cost_egp=17.0,
                platform_commission_egp=3.4,
                distance_fee_egp=3.0,
                safety_margin_egp=5.0,
                fair_price_per_seat=50.0,
            )

        assert exc_info.value.code == "group_archived"
        assert exc_info.value.status_code == 403
