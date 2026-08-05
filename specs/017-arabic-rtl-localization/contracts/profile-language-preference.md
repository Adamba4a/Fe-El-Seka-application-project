# Contract: Profile Language Preference

Extends the existing profile-update surface — no new endpoint.

## `PATCH /profiles/me`

**Existing endpoint** (`services/api/app/api/profiles/router.py`), request body gains one optional
field.

### Request

```json
{
  "display_name": "string (optional, unchanged)",
  "language_preference": "en | ar (optional, NEW)"
}
```

- `language_preference` omitted → no change to the stored value.
- `language_preference` present → MUST be exactly `"en"` or `"ar"`; any other value is a 422
  validation error (enforced by the existing Pydantic `ProfileUpdate` model's `Literal["en", "ar"]`,
  same validation pattern as `display_name`'s existing length check).

### Response

`ProfileResponse` (existing shape) gains:

```json
{
  "...": "...existing fields unchanged...",
  "language_preference": "en | ar | null"
}
```

`null` indicates no explicit choice has been made yet (see `data-model.md` — this is the FR-013
prompt-trigger state, distinct from an error).

### Behavior

- Setting `language_preference` takes effect immediately for that user's next request (locale
  resolution in `middleware.ts` reads the live `profiles` row — see `research.md` R2) — no
  separate cache invalidation step required, since `middleware.ts` already queries `profiles`
  per-request for verification-status gating.
- This is the same call site used by both the Settings toggle (`ProfileEditor.tsx` /
  `LanguageSection`) and the one-time prompt (`LanguagePromptModal.tsx`) — there is no separate
  "prompt-only" endpoint.

### Errors

| Status | Condition |
|---|---|
| 401 | No valid session (existing behavior, unchanged) |
| 422 | `language_preference` present but not `"en"`/`"ar"` |

No new error cases introduced beyond the existing `PATCH /profiles/me` error surface.
