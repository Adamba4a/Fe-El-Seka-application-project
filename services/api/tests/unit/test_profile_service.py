from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.profile import ProfileUpdate
from app.services import profile_service as svc


# ── ProfileUpdate.phone_number: format validation (Spec 020, FR-002/FR-011) ──


class TestProfileUpdatePhoneNumberValidation:
    @pytest.mark.parametrize("value", ["+201234567", "+15551234567", "+9491234567890"])
    def test_accepts_valid_formats(self, value):
        assert ProfileUpdate(phone_number=value).phone_number == value

    def test_none_is_allowed(self):
        assert ProfileUpdate(phone_number=None).phone_number is None

    def test_field_omitted_defaults_to_none(self):
        assert ProfileUpdate().phone_number is None

    @pytest.mark.parametrize(
        "value", ["0123456789", "not-a-phone", "+1", "+0123456789", "12345"]
    )
    def test_rejects_invalid_formats(self, value):
        with pytest.raises(ValidationError):
            ProfileUpdate(phone_number=value)

    def test_strips_surrounding_whitespace(self):
        assert ProfileUpdate(phone_number="  +201234567  ").phone_number == "+201234567"


# ── update_profile: phone_number persistence ─────────────────────────────────


class _FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class _FakeUpdateQuery:
    def __init__(self, table, payload):
        self.table = table
        self.payload = payload
        self.filters: dict = {}

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        self.table.captured_updates.append((self.payload, dict(self.filters)))
        row = dict(self.table.row)
        row.update(self.payload)
        return _FakeExecuteResult([row])


class _FakeTable:
    def __init__(self, name, row):
        self.name = name
        self.row = row
        self.captured_updates: list[tuple[dict, dict]] = []

    def update(self, payload):
        return _FakeUpdateQuery(self, payload)


class _FakeSupabase:
    def __init__(self, row):
        self._table = _FakeTable("profiles", row)

    def table(self, name):
        assert name == "profiles"
        return self._table


def _base_row():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "phone_number": None,
        "display_name": "Old Name",
        "role": "passenger",
        "profile_photo_path": None,
        "verification_status": "unverified",
        "is_submission_locked": False,
        "rating_avg": None,
        "rating_count": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "language_preference": None,
    }


class TestUpdateProfilePersistsPhoneNumber:
    def test_includes_phone_number_in_update_payload_when_provided(self, monkeypatch):
        fake = _FakeSupabase(_base_row())
        monkeypatch.setattr(svc, "_supabase", lambda: fake)

        result = svc.update_profile("user-1", None, None, "+201234567890")

        payload, filters = fake._table.captured_updates[0]
        assert payload == {"phone_number": "+201234567890"}
        assert filters == {"id": "user-1"}
        assert result["phone_number"] == "+201234567890"

    def test_omits_phone_number_from_payload_when_not_provided(self, monkeypatch):
        fake = _FakeSupabase(_base_row())
        monkeypatch.setattr(svc, "_supabase", lambda: fake)

        svc.update_profile("user-1", "New Name", None, None)

        payload, _ = fake._table.captured_updates[0]
        assert payload == {"display_name": "New Name"}
        assert "phone_number" not in payload
