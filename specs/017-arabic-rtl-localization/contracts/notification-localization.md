# Contract: Notification Localization

Internal contract — governs how `services/api/app/services/fcm_service.py` selects push-notification
content. Not a public API; documented because it's a behavior change other backend code (anything
calling `send_push_notifications()`) implicitly depends on.

## `_NOTIFICATION_TEMPLATES` shape

**Before**:

```python
dict[str, tuple[str, str]]   # event_type -> (title, body)
```

**After**:

```python
dict[str, dict[str, tuple[str, str]]]   # event_type -> locale -> (title, body)
```

### Contract for callers

- Callers of `send_push_notifications(conn, recipient_user_id, event_type, data_payload)` are
  **unaffected** — the function signature does not change. Locale selection happens inside the
  function.
- Every `event_type` key present in `_NOTIFICATION_TEMPLATES` MUST have both `"en"` and `"ar"`
  entries. This is a data-completeness contract, not enforced by a runtime check in this iteration
  (mirrors how the existing flat dict has no runtime completeness check either) — verified instead by
  a unit test that asserts every event_type has both locale keys (`test_fcm_service.py`).
- The fallback default `("Triplyy", "You have a new notification.")` (used today for unknown
  `event_type`s) becomes locale-aware too: `{"en": ("Triplyy", "..."), "ar": ("...", "...")}`,
  selected the same way as named event types.

### Locale selection logic

```
locale = profiles.language_preference for recipient_user_id
if locale is None:
    locale = "en"   # FR-011 fallback principle applied to notification content
title, body = _NOTIFICATION_TEMPLATES[event_type][locale]
```

Requires one additional column read on the existing per-notification `profiles`/device-token query
path in `send_push_notifications()` — no new query round-trip, since that function already needs to
look up the recipient before sending.

### Explicitly out of contract

- OTP/auth SMS delivery — separate code path, untouched (FR-014, spec Out-of-Scope).
- In-app notification *display* (if/when a notification inbox UI exists) — governed by the message
  catalog contract instead, not this one; this contract covers push payload content only.
