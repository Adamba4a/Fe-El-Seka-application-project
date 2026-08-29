from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.group import DomainVerificationConfirm, DomainVerificationRequest
from app.services import group_service

# ── shared fakes (same query-substring-routing convention as
# tests/integration/test_rides_fare_override.py) ────────────────────────────


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
    """Routes fetchval/fetchrow/execute calls by matching an ordered list of
    (substring, response) rules against the query text. `response` may be a
    plain value or a zero-arg callable (for dynamic/exception responses)."""

    def __init__(self, fetchval_rules=None, fetchrow_rules=None, execute_rules=None):
        self._fetchval_rules = fetchval_rules or []
        self._fetchrow_rules = fetchrow_rules or []
        self._execute_rules = execute_rules or []
        self.executed_queries: list[str] = []

    def _resolve(self, rules, query):
        for substring, response in rules:
            if substring in query:
                return response() if callable(response) else response
        raise AssertionError(f"Unmatched query: {query}")

    async def fetchval(self, query, *args):
        return self._resolve(self._fetchval_rules, query)

    async def fetchrow(self, query, *args):
        return self._resolve(self._fetchrow_rules, query)

    async def execute(self, query, *args):
        self.executed_queries.append(query)
        return self._resolve(self._execute_rules, query) if self._execute_rules else "OK"

    def transaction(self):
        return _FakeTransactionCtx()


def _group_summary_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "name": "Test Group",
        "type": "general",
        "description": None,
        "route_tags": [],
        "member_count": 2,
    }
    row.update(overrides)
    return row


# ── leave_group (T047) ───────────────────────────────────────────────────────


class TestLeaveGroup:
    async def test_member_leaves_successfully(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM group_memberships", {"role": "member"})],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        await group_service.leave_group(uuid.uuid4(), uuid.uuid4())

        assert any("DELETE FROM group_memberships" in q for q in conn.executed_queries)

    async def test_owner_leaves_with_no_other_members_succeeds(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM group_memberships", {"role": "owner"})],
            fetchval_rules=[("user_id != $2", None)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        await group_service.leave_group(uuid.uuid4(), uuid.uuid4())

        assert any("DELETE FROM group_memberships" in q for q in conn.executed_queries)

    async def test_owner_leaves_with_other_members_requires_transfer(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM group_memberships", {"role": "owner"})],
            fetchval_rules=[("user_id != $2", 1)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.leave_group(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "ownership_transfer_required"

    async def test_non_member_leaving_is_rejected(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM group_memberships", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.leave_group(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "not_a_group_member"


# ── remove_member (T049) ─────────────────────────────────────────────────────


class TestRemoveMember:
    async def test_owner_removes_member_successfully(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": owner_id})],
            execute_rules=[("DELETE FROM group_memberships", "DELETE 1")],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        await group_service.remove_member(uuid.uuid4(), owner_id, uuid.uuid4())

    async def test_non_owner_cannot_remove(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": uuid.uuid4()})],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.remove_member(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "not_group_owner"

    async def test_owner_cannot_remove_self(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": owner_id})],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.remove_member(uuid.uuid4(), owner_id, owner_id)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "cannot_remove_owner"

    async def test_removing_non_member_returns_404(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": owner_id})],
            execute_rules=[("DELETE FROM group_memberships", "DELETE 0")],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.remove_member(uuid.uuid4(), owner_id, uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "not_a_group_member"

    async def test_group_not_found(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.remove_member(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "group_not_found"


# ── transfer_ownership (T050) ────────────────────────────────────────────────


class TestTransferOwnership:
    async def test_happy_path(self, monkeypatch):
        owner_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        summary_row = _group_summary_row()
        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("FROM groups", {"owner_id": owner_id}),
                ("UPDATE groups SET owner_id", summary_row),
            ],
            fetchval_rules=[("FROM group_memberships", 1)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        result = await group_service.transfer_ownership(uuid.uuid4(), owner_id, str(new_owner_id))

        assert result.id == str(summary_row["id"])
        assert any("role = 'member'" in q for q in conn.executed_queries)
        assert any("role = 'owner'" in q for q in conn.executed_queries)

    async def test_new_owner_must_be_a_member(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM groups", {"owner_id": owner_id})],
            fetchval_rules=[("FROM group_memberships", None)],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.transfer_ownership(uuid.uuid4(), owner_id, str(uuid.uuid4()))

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "not_a_group_member"

    async def test_cannot_transfer_to_self(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": owner_id})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.transfer_ownership(uuid.uuid4(), owner_id, str(owner_id))

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "already_owner"

    async def test_non_owner_cannot_transfer(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": uuid.uuid4()})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.transfer_ownership(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()))

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "not_group_owner"

    async def test_invalid_new_owner_uuid_rejected(self, monkeypatch):
        # Validated before the pool is ever touched — a poisoned pool proves this.
        def _boom():
            raise AssertionError("pool should not be acquired for an invalid uuid")

        monkeypatch.setattr(group_service, "get_pool", _boom)

        with pytest.raises(HTTPException) as exc_info:
            await group_service.transfer_ownership(uuid.uuid4(), uuid.uuid4(), "not-a-uuid")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "invalid_user_id"

    async def test_group_not_found(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.transfer_ownership(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()))

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "group_not_found"


# ── archive_group (T051) ─────────────────────────────────────────────────────


class TestArchiveGroup:
    async def test_owner_archives_successfully(self, monkeypatch):
        owner_id = uuid.uuid4()
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": owner_id})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        await group_service.archive_group(uuid.uuid4(), owner_id)

        assert any("archived_at = now()" in q for q in conn.executed_queries)

    async def test_non_owner_cannot_archive(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", {"owner_id": uuid.uuid4()})])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.archive_group(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "not_group_owner"

    async def test_group_not_found_or_already_archived(self, monkeypatch):
        conn = _RoutedFakeConn(fetchrow_rules=[("FROM groups", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.archive_group(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "group_not_found"


# ── list_group_members ───────────────────────────────────────────────────────


class TestListGroupMembers:
    async def test_member_can_list_members(self, monkeypatch):
        user_id = uuid.uuid4()
        member_row = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "display_name": "Sara",
            "role": "owner",
            "joined_at": datetime.now(timezone.utc),
        }
        conn = _RoutedFakeConn(
            fetchval_rules=[
                ("FROM groups WHERE id", 1),
                ("FROM group_memberships", 1),
            ],
        )

        async def _fetch(query, *args):
            assert "JOIN profiles" in query
            return [member_row]

        conn.fetch = _fetch
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        result = await group_service.list_group_members(uuid.uuid4(), user_id)

        assert len(result) == 1
        assert result[0].display_name == "Sara"
        assert result[0].role == "owner"

    async def test_non_member_cannot_list_members(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchval_rules=[
                ("FROM groups WHERE id", 1),
                ("FROM group_memberships", None),
            ],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.list_group_members(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "not_a_group_member"

    async def test_group_not_found(self, monkeypatch):
        conn = _RoutedFakeConn(fetchval_rules=[("FROM groups WHERE id", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        with pytest.raises(HTTPException) as exc_info:
            await group_service.list_group_members(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "group_not_found"


# ── domain verification: blocklist + rate limit (Phase 6, re-verified here) ─


class TestDomainVerificationGuards:
    async def test_blocklisted_domain_rejected(self, monkeypatch):
        conn = _RoutedFakeConn(fetchval_rules=[("platform_settings", None)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        payload = DomainVerificationRequest(email="user@gmail.com", requested_group_type="company")
        profile = {"id": str(uuid.uuid4()), "verification_status": "verified"}

        with pytest.raises(HTTPException) as exc_info:
            await group_service.request_domain_verification(profile, payload)

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "blocklisted_domain"

    async def test_unverified_identity_blocked_before_domain_check(self, monkeypatch):
        payload = DomainVerificationRequest(email="user@newco.com", requested_group_type="company")
        profile = {"id": str(uuid.uuid4()), "verification_status": "pending"}

        with pytest.raises(HTTPException) as exc_info:
            await group_service.request_domain_verification(profile, payload)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "identity_verification_required"

    async def test_new_domain_registration_rate_limited(self, monkeypatch):
        verification_id = uuid.uuid4()
        user_id = uuid.uuid4()
        salt = "s" * 16
        code = "123456"
        otp_hash = f"{salt}${group_service._hash_otp(code, salt)}"

        verification_row = {
            "id": verification_id,
            "domain": "newco.com",
            "requested_group_type": "company",
            "otp_code_hash": otp_hash,
            "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "verified_at": None,
            "is_first_for_domain": True,
        }

        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("FOR UPDATE", verification_row),
                ("FROM groups WHERE domain", None),
            ],
            fetchval_rules=[
                ("COUNT(*)", 5),
                ("platform_settings", None),
            ],
            execute_rules=[
                ("UPDATE domain_verifications SET verified_at", "UPDATE 1"),
                ("UPDATE profiles", "UPDATE 1"),
            ],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        payload = DomainVerificationConfirm(verification_id=str(verification_id), code=code)
        profile = {"id": str(user_id), "verification_status": "verified"}

        with pytest.raises(HTTPException) as exc_info:
            await group_service.confirm_domain_verification(profile, payload)

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["error"] == "domain_registration_rate_limited"

    async def test_confirm_sets_org_verified_at_when_not_already_set(self, monkeypatch):
        verification_id = uuid.uuid4()
        user_id = uuid.uuid4()
        group_id = uuid.uuid4()
        salt = "s" * 16
        code = "123456"
        otp_hash = f"{salt}${group_service._hash_otp(code, salt)}"

        verification_row = {
            "id": verification_id,
            "domain": "newco.com",
            "requested_group_type": "company",
            "otp_code_hash": otp_hash,
            "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "verified_at": None,
            "is_first_for_domain": False,
        }
        new_group_row = _group_summary_row(id=group_id, name="Newco", owner_id=user_id, member_count=0)
        membership_row = {
            "id": uuid.uuid4(),
            "group_id": group_id,
            "user_id": user_id,
            "role": "owner",
            "joined_at": datetime.now(timezone.utc),
        }
        final_group_row = _group_summary_row(id=group_id, name="Newco", owner_id=user_id, member_count=1)

        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("FOR UPDATE", verification_row),
                ("FROM groups WHERE domain", None),
                ("INSERT INTO groups", new_group_row),
                ("FROM group_memberships WHERE group_id = $1 AND user_id = $2", membership_row),
                ("FROM groups WHERE id = $1", final_group_row),
            ],
            execute_rules=[
                ("UPDATE domain_verifications SET verified_at", "UPDATE 1"),
                ("UPDATE profiles", "UPDATE 1"),
                ("INSERT INTO group_memberships", "INSERT 1"),
            ],
        )
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        payload = DomainVerificationConfirm(verification_id=str(verification_id), code=code)
        profile = {"id": str(user_id), "verification_status": "verified"}

        await group_service.confirm_domain_verification(profile, payload)

        org_verified_updates = [
            q for q in conn.executed_queries if "UPDATE profiles" in q and "org_verified_at" in q
        ]
        assert len(org_verified_updates) == 1
        assert "org_verified_at IS NULL" in org_verified_updates[0]

    async def test_already_used_verification_id_rejected(self, monkeypatch):
        verification_id = uuid.uuid4()
        user_id = uuid.uuid4()
        verification_row = {
            "id": verification_id,
            "domain": "newco.com",
            "requested_group_type": "company",
            "otp_code_hash": "irrelevant$irrelevant",
            "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "verified_at": datetime.now(timezone.utc),
            "is_first_for_domain": True,
        }
        conn = _RoutedFakeConn(fetchrow_rules=[("FOR UPDATE", verification_row)])
        monkeypatch.setattr(group_service, "get_pool", lambda: _FakePool(conn))

        payload = DomainVerificationConfirm(verification_id=str(verification_id), code="000000")
        profile = {"id": str(user_id), "verification_status": "verified"}

        with pytest.raises(HTTPException) as exc_info:
            await group_service.confirm_domain_verification(profile, payload)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "otp_already_used"
