from __future__ import annotations

from app.services import fcm_service as svc

# ── _NOTIFICATION_TEMPLATES: data-completeness contract ─────────────────────
# per contracts/notification-localization.md: every event_type must have both
# "en" and "ar" entries, and the unknown-event fallback must too.


class TestNotificationTemplatesCompleteness:
    def test_every_event_type_has_both_locales(self):
        for event_type, locales in svc._NOTIFICATION_TEMPLATES.items():
            assert "en" in locales, f"{event_type} missing 'en' template"
            assert "ar" in locales, f"{event_type} missing 'ar' template"

    def test_every_template_has_nonempty_title_and_body(self):
        for event_type, locales in svc._NOTIFICATION_TEMPLATES.items():
            for locale, (title, body) in locales.items():
                assert title.strip(), f"{event_type}/{locale} has empty title"
                assert body.strip(), f"{event_type}/{locale} has empty body"

    def test_default_template_has_both_locales(self):
        assert "en" in svc._DEFAULT_TEMPLATE
        assert "ar" in svc._DEFAULT_TEMPLATE


# ── _select_template: locale-selection + NULL-preference fallback ───────────


class TestSelectTemplate:
    def test_selects_requested_locale(self):
        title, body = svc._select_template("ride_completed", "ar")
        assert (title, body) == svc._NOTIFICATION_TEMPLATES["ride_completed"]["ar"]

    def test_null_preference_falls_back_to_english(self):
        title, body = svc._select_template("ride_completed", None)
        assert (title, body) == svc._NOTIFICATION_TEMPLATES["ride_completed"]["en"]

    def test_unknown_event_type_uses_default_template(self):
        title, body = svc._select_template("some_future_event_type", "en")
        assert (title, body) == svc._DEFAULT_TEMPLATE["en"]

    def test_unknown_event_type_with_null_preference_falls_back_to_default_english(self):
        title, body = svc._select_template("some_future_event_type", None)
        assert (title, body) == svc._DEFAULT_TEMPLATE["en"]
