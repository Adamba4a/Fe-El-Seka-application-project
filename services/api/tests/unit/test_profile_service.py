from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.profile import ProfileUpdate
from app.services import profile_service as svc


# ── ProfileUpdate.phone_number: format validation (Spec 020, FR-002/FR-011) ──


class TestProfileUpdatePhoneNumberValidation:
    @pytest.mark.parametrize("value", ["+201234567890", "+201012345678", "+201555555555"])
    def test_accepts_valid_formats(self, value):
        assert ProfileUpdate(phone_number=value).phone_number == value

    def test_none_is_allowed(self):
        assert ProfileUpdate(phone_number=None).phone_number is None

    def test_field_omitted_defaults_to_none(self):
        assert ProfileUpdate().phone_number is None

    @pytest.mark.parametrize(
        "value",
        [
            "0123456789",
            "not-a-phone",
            "+1",
            "+0123456789",
            "12345",
            "+201234567",  # too short: 9 digits after +2, needs 11
            "+2012345678901",  # too long: 13 digits after +2
            "+15551234567",  # non-Egyptian country code
        ],
    )
    def test_rejects_invalid_formats(self, value):
        with pytest.raises(ValidationError):
            ProfileUpdate(phone_number=value)

    def test_strips_surrounding_whitespace(self):
        assert ProfileUpdate(phone_number="  +201234567890  ").phone_number == "+201234567890"


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


# ── update_profile: date_of_birth minimum-age gate (Spec 021, FR-002/FR-017) ─


class TestUpdateProfileMinimumAge:
    def test_persists_date_of_birth_when_of_age(self, monkeypatch):
        fake = _FakeSupabase(_base_row())
        monkeypatch.setattr(svc, "_supabase", lambda: fake)
        dob = date(date.today().year - 25, 1, 1)

        result = svc.update_profile("user-1", None, None, None, dob)

        payload, _ = fake._table.captured_updates[0]
        assert payload == {"date_of_birth": dob.isoformat()}
        assert result["date_of_birth"] == dob.isoformat()

    def test_rejects_date_of_birth_under_minimum_age(self, monkeypatch):
        fake = _FakeSupabase(_base_row())
        monkeypatch.setattr(svc, "_supabase", lambda: fake)
        today = date.today()
        dob = date(today.year - 17, today.month, today.day)

        with pytest.raises(HTTPException) as exc_info:
            svc.update_profile("user-1", None, None, None, dob)

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "underage"
        assert fake._table.captured_updates == []

    def test_accepts_date_of_birth_on_exact_birthday_at_minimum_age(self, monkeypatch):
        fake = _FakeSupabase(_base_row())
        monkeypatch.setattr(svc, "_supabase", lambda: fake)
        today = date.today()
        dob = date(today.year - svc.MIN_SIGNUP_AGE_YEARS, today.month, today.day)

        result = svc.update_profile("user-1", None, None, None, dob)

        assert result["date_of_birth"] == dob.isoformat()
