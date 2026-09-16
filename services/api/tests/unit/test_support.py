from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.support import admin_router, router
from app.dependencies.auth import get_current_user
from app.models.support import SupportRequest
from app.services import notification_service
from app.services import support_service as service


def payload(**kwargs):
    return {"id": str(uuid4()), "email": "person@example.com", "description": "Cannot finish signup", **kwargs}


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "bad"},
        {"email": "a@b"},
        {"email": "a\r\n@example.com"},
        {"email": ".name@example.com"},
        {"email": "a..b@example.com"},
        {"description": " " * 10},
        {"description": "a" * 5001},
        {"locale": "fr"},
    ],
)
def test_invalid_input(changes):
    with pytest.raises(ValidationError):
        SupportRequest(**payload(**changes))


def test_normalizes_and_accepts_arabic():
    body = SupportRequest(**payload(email=" Person@Example.com ", description="  مش قادر أكمل التسجيل  ", locale="ar"))
    assert body.email == "person@example.com"
    assert body.description == "مش قادر أكمل التسجيل"


class Connection:
    def __init__(self):
        self.execute = AsyncMock()
        self.fetchval = AsyncMock(return_value=None)
        self.fetchrow = AsyncMock(return_value={"email_count": 0, "client_count": 0})

    @asynccontextmanager
    async def transaction(self):
        yield


@pytest.fixture
def conn(monkeypatch):
    connection = Connection()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection

    monkeypatch.setattr(service, "get_pool", lambda: Pool())
    return connection


async def test_submit_stores_without_sending_email(conn, monkeypatch):
    send = AsyncMock()
    monkeypatch.setattr(service, "_send_email", send)
    body = SupportRequest(**payload())
    assert await service.submit_report(body, "127.0.0.1") == {"id": body.id}
    args = conn.execute.call_args.args
    assert "INSERT INTO support_requests" in args[0]
    assert args[2] == body.email
    assert len(args[5]) == 64 and args[5] != "127.0.0.1"
    send.assert_not_called()


async def test_duplicate_does_not_insert_or_consume_limit(conn):
    body = SupportRequest(**payload())
    conn.fetchval.return_value = body.id
    assert await service.submit_report(body, "127.0.0.1") == {"id": body.id}
    assert conn.execute.call_count == 1  # lock only
    conn.fetchrow.assert_not_called()


@pytest.mark.parametrize("counts", [{"email_count": 3, "client_count": 3}, {"email_count": 0, "client_count": 10}])
async def test_limits_block_inserts(conn, counts):
    conn.fetchrow.return_value = counts
    with pytest.raises(HTTPException) as exc:
        await service.submit_report(SupportRequest(**payload()), "127.0.0.1")
    assert exc.value.status_code == 429
    assert conn.execute.call_count == 1


async def test_honeypot_rejected_before_database(conn):
    with pytest.raises(HTTPException):
        await service.submit_report(SupportRequest(**payload(website="spam")), "127.0.0.1")
    conn.execute.assert_not_called()


async def test_status_change_is_audited(conn):
    conn.fetchval.return_value = "open"
    report_id, admin_id = uuid4(), uuid4()
    await service.update_status(report_id, "resolved", admin_id)
    assert conn.execute.call_count == 2
    assert conn.execute.call_args.args[1:] == (report_id, admin_id, "open", "resolved")


async def test_missing_report_is_404(conn):
    with pytest.raises(HTTPException) as exc:
        await service.update_status(uuid4(), "resolved", uuid4())
    assert exc.value.status_code == 404
    conn.execute.assert_not_called()


@pytest.mark.parametrize("attempts,expected", [(0, "pending"), (4, "failed")])
async def test_email_failure_keeps_report_and_retries(conn, monkeypatch, attempts, expected):
    row = {**payload(description="<script>alert(1)</script>"), "locale": "ar", "email_attempts": attempts}
    conn.fetchrow.side_effect = [row, None]
    monkeypatch.setattr(service, "_send_email", AsyncMock(side_effect=RuntimeError("provider offline")))
    await service.process_support_emails()
    assert conn.execute.call_args.args[2] == expected
    assert conn.execute.call_args.args[3] == attempts + 1


async def test_email_success_escapes_content_and_uses_support_inbox(conn, monkeypatch):
    row = {**payload(description="<script>alert(1)</script>"), "locale": "ar", "email_attempts": 0}
    conn.fetchrow.side_effect = [row, None]
    send = AsyncMock()
    monkeypatch.setattr(service, "_send_email", send)
    await service.process_support_emails()
    assert send.call_args.args[0] == service.settings.support_email
    assert "<script>" not in send.call_args.args[2]
    assert "&lt;script&gt;" in send.call_args.args[2]
    assert "email_status='sent'" in conn.execute.call_args.args[0]


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router, prefix="/api/support")
    application.include_router(admin_router, prefix="/api/admin/support")
    return application


def test_public_submit_and_validation(app, monkeypatch):
    mock = AsyncMock(return_value={"id": str(uuid4())})
    monkeypatch.setattr(service, "submit_report", mock)
    client = TestClient(app)
    assert client.post("/api/support", json=payload()).status_code == 201
    assert client.post("/api/support", json=payload(email="invalid")).status_code == 422
    assert mock.call_count == 1


def test_admin_routes_reject_anonymous_and_regular_users(app):
    client = TestClient(app)
    assert client.get("/api/admin/support").status_code in (401, 403)
    assert client.patch(f"/api/admin/support/{uuid4()}", json={"status": "resolved"}).status_code in (401, 403)
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "passenger"}
    assert client.get("/api/admin/support").status_code == 403
    assert client.patch(f"/api/admin/support/{uuid4()}", json={"status": "resolved"}).status_code == 403


def test_admin_filter_and_status_validation(app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin"}
    monkeypatch.setattr(service, "list_reports", AsyncMock(return_value={"items": [], "total": 0, "page": 1}))
    client = TestClient(app)
    assert client.get("/api/admin/support?status=open").status_code == 200
    assert client.get("/api/admin/support?status=invalid").status_code == 422
    assert client.get("/api/admin/support?page=0").status_code == 422
    assert client.patch(f"/api/admin/support/{uuid4()}", json={"status": "invalid"}).status_code == 422


async def test_existing_email_transport_sends_through_resend(monkeypatch):
    from unittest.mock import Mock

    send = Mock(return_value={"id": "test-message"})
    monkeypatch.setattr(notification_service, "_use_mailpit", lambda: False)
    monkeypatch.setattr(notification_service.resend.Emails, "send", send)
    await notification_service._send_email("support@example.com", "Test", "<p>Message</p>")
    assert send.call_args.args[0]["to"] == "support@example.com"
    assert send.call_args.args[0]["html"] == "<p>Message</p>"


async def test_existing_email_transport_propagates_failure_for_retry(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr(notification_service, "_use_mailpit", lambda: False)
    monkeypatch.setattr(notification_service.resend.Emails, "send", Mock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError, match="offline"):
        await notification_service._send_email("support@example.com", "Test", "<p>Message</p>")
