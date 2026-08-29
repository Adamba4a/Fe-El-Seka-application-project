from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.org_access import OrgAccessConfirm, OrgAccessRequest
from app.services import org_access_service
from app.services.domain_verification_service import _hash_otp

# ── shared fakes (same query-substring-routing convention as
# tests/unit/test_group_service.py) ─────────────────────────────────────────


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
    def __init__(self, fetchval_rules=None, fetchrow_rules=None, execute_rules=None):
        self._fetchval_rules = fetchval_rules or []
        self._fetchrow_rules = fetchrow_rules or []
        self._execute_rules = execute_rules or []

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
        return self._resolve(self._execute_rules, query) if self._execute_rules else "OK"

    def transaction(self):
        return _FakeTransactionCtx()


async def _noop_send_email(*args, **kwargs):
    return None


# ── request_verification (T013) ─────────────────────────────────────────────


class TestRequestVerification:
    async def test_success(self, monkeypatch):
        verification_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchval_rules=[("platform_settings", None)],
            fetchrow_rules=[("INSERT INTO domain_verifications", {"id": verification_id})],
        )
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))
        monkeypatch.setattr(
            org_access_service.notification_service,
            "send_domain_verification_email",
            _noop_send_email,
        )

        profile = {"id": str(uuid.uuid4())}
        payload = OrgAccessRequest(email="user@newco.com")

        result = await org_access_service.request_verification(profile, payload)

        assert result.verification_id == str(verification_id)
        assert result.expires_in_seconds == 300

    async def test_succeeds_even_when_email_verified_on_another_account(self, monkeypatch):
        # FR-010 / Scenario 7: the email-uniqueness conflict is enforced only
        # at confirm-time. request_verification issues no query beyond the
        # blocklist check, so a fetchval call for anything else here would
        # hit the fake's "unmatched query" AssertionError instead of this
        # test's assertions — proving no conflict check happens on request.
        verification_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchval_rules=[("platform_settings", None)],
            fetchrow_rules=[("INSERT INTO domain_verifications", {"id": verification_id})],
        )
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))
        monkeypatch.setattr(
            org_access_service.notification_service,
            "send_domain_verification_email",
            _noop_send_email,
        )

        profile = {"id": str(uuid.uuid4())}
        payload = OrgAccessRequest(email="shared@dept.acme-corp.com")

        result = await org_access_service.request_verification(profile, payload)

        assert result.verification_id == str(verification_id)

    async def test_invalid_email(self):
        profile = {"id": str(uuid.uuid4())}
        payload = OrgAccessRequest(email="not-an-email")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.request_verification(profile, payload)

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "invalid_email"

    @pytest.mark.parametrize(
        "domain",
        ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "protonmail.com"],
    )
    async def test_blocklisted_domain(self, monkeypatch, domain):
        # No fetchrow_rules: if the code reached the OTP-insert step for a
        # blocklisted domain, this fake would raise AssertionError on the
        # unmatched query instead of the expected HTTPException below —
        # proving no OTP is generated for a rejected domain.
        conn = _RoutedFakeConn(fetchval_rules=[("platform_settings", None)])
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(uuid.uuid4())}
        payload = OrgAccessRequest(email=f"user@{domain}")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.request_verification(profile, payload)

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "blocklisted_domain"

    async def test_otp_rate_limited(self, monkeypatch):
        conn = _RoutedFakeConn(
            fetchval_rules=[("platform_settings", None)],
            fetchrow_rules=[("INSERT INTO domain_verifications", lambda: {"id": uuid.uuid4()})],
        )
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))
        monkeypatch.setattr(
            org_access_service.notification_service,
            "send_domain_verification_email",
            _noop_send_email,
        )

        profile = {"id": str(uuid.uuid4())}
        # Same email each time — the resend limiter keys on email, not user.
        payload = OrgAccessRequest(email="rate-limit-target@newco.com")

        for _ in range(3):
            await org_access_service.request_verification(profile, payload)

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.request_verification(profile, payload)

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["error"] == "otp_rate_limited"


# ── confirm_verification (T014) ─────────────────────────────────────────────


def _verification_row(**overrides):
    code = "123456"
    salt = "s" * 16
    row = {
        "id": uuid.uuid4(),
        "email": "user@newco.com",
        "domain": "newco.com",
        "otp_code_hash": f"{salt}${_hash_otp(code, salt)}",
        "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "verified_at": None,
    }
    row.update(overrides)
    return row


class TestConfirmVerification:
    async def test_success_sets_org_verified_at(self, monkeypatch):
        user_id = uuid.uuid4()
        verification = _verification_row()
        verified_at = datetime.now(timezone.utc)

        conn = _RoutedFakeConn(
            fetchrow_rules=[
                ("FOR UPDATE", verification),
                ("RETURNING org_verified_at", {
                    "org_verified_at": verified_at,
                    "org_verified_domain": "newco.com",
                }),
            ],
            fetchval_rules=[("FROM profiles p", None)],
            execute_rules=[("UPDATE domain_verifications SET verified_at", "UPDATE 1")],
        )
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(user_id)}
        payload = OrgAccessConfirm(verification_id=str(verification["id"]), code="123456")

        result = await org_access_service.confirm_verification(profile, payload)

        assert result.org_verified_at == verified_at.isoformat()
        assert result.org_verified_domain == "newco.com"

    async def test_email_already_verified_elsewhere_conflict(self, monkeypatch):
        # FR-010 / Scenario 7: this conflict is only ever raised here, at
        # confirm-time — never at request-time (see
        # TestRequestVerification.test_succeeds_even_when_email_verified_on_another_account).
        user_id = uuid.uuid4()
        verification = _verification_row()

        conn = _RoutedFakeConn(
            fetchrow_rules=[("FOR UPDATE", verification)],
            fetchval_rules=[("FROM profiles p", 1)],
        )
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(user_id)}
        payload = OrgAccessConfirm(verification_id=str(verification["id"]), code="123456")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.confirm_verification(profile, payload)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "email_already_verified_elsewhere"

    async def test_otp_invalid_wrong_code(self, monkeypatch):
        user_id = uuid.uuid4()
        verification = _verification_row()
        conn = _RoutedFakeConn(fetchrow_rules=[("FOR UPDATE", verification)])
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(user_id)}
        payload = OrgAccessConfirm(verification_id=str(verification["id"]), code="000000")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.confirm_verification(profile, payload)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "otp_invalid"

    async def test_otp_already_used(self, monkeypatch):
        user_id = uuid.uuid4()
        verification = _verification_row(verified_at=datetime.now(timezone.utc))
        conn = _RoutedFakeConn(fetchrow_rules=[("FOR UPDATE", verification)])
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(user_id)}
        payload = OrgAccessConfirm(verification_id=str(verification["id"]), code="123456")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.confirm_verification(profile, payload)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "otp_already_used"

    async def test_otp_expired(self, monkeypatch):
        user_id = uuid.uuid4()
        verification = _verification_row(
            otp_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        conn = _RoutedFakeConn(fetchrow_rules=[("FOR UPDATE", verification)])
        monkeypatch.setattr(org_access_service, "get_pool", lambda: _FakePool(conn))

        profile = {"id": str(user_id)}
        payload = OrgAccessConfirm(verification_id=str(verification["id"]), code="123456")

        with pytest.raises(HTTPException) as exc_info:
            await org_access_service.confirm_verification(profile, payload)

        assert exc_info.value.status_code == 410
        assert exc_info.value.detail["error"] == "otp_expired"
