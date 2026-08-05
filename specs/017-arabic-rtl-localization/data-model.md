# Phase 1 Data Model: Arabic & RTL Localization

## Entity: `profiles.language_preference` (column addition)

Extends the existing `public.profiles` table (`supabase/migrations/20260614000001_create_profiles.sql`).

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `language_preference` | `TEXT` | `NULL` allowed; `CHECK (language_preference IN ('en', 'ar'))` when not NULL | `NULL` = no explicit choice made yet. Drives FR-004 (persist across sessions/devices), FR-005 (unauthenticated fallback happens client/cookie-side, not via this column), and FR-013 (NULL triggers the one-time prompt — see `research.md` R5). |

**Migration**: `supabase/migrations/20260805000001_phase14_language_preference.sql`

```sql
ALTER TABLE public.profiles
    ADD COLUMN language_preference TEXT
        CHECK (language_preference IN ('en', 'ar'));
```

No default value and no backfill — existing rows land as `NULL`, which is exactly the "prompt on next
login" trigger condition from FR-013/R5. New signups during onboarding may write a non-NULL value
immediately (carried over from the pre-auth `NEXT_LOCALE` cookie choice at signup time), so most new
users never see the prompt at all.

**State transitions**: `NULL → 'en' | 'ar'` (first explicit choice, via prompt or Settings toggle),
then `'en' ↔ 'ar'` (toggled freely thereafter, per FR-002/FR-012). No other states; not soft-deleted
or versioned — this is a live preference, not an auditable record (unlike verification or financial
data under the constitution's Data Standards, which this is not).

## Entity: Locale (application-level, not persisted)

Not a database entity — the resolved-per-request display locale. Represented as a simple union type,
shared across frontend and (conceptually) the FCM template lookup:

```ts
// packages/shared/src/types/user.ts (extension)
export type Locale = "en" | "ar";
```

**Resolution order** (implemented in `apps/main/src/middleware.ts`, see `plan.md` Project Structure):

1. Authenticated user: `profiles.language_preference` (if not `NULL`)
2. `NEXT_LOCALE` cookie (unauthenticated visitors, or authenticated users mid-prompt before their
   first explicit choice)
3. Default: `"ar"` (spec Assumptions — Egypt is the primary market)

## Entity: `Profile` (existing type extension)

`packages/shared/src/types/user.ts`

```ts
export interface Profile {
  // ...existing fields unchanged...
  language_preference: "en" | "ar" | null;   // NEW
}

export interface ProfileUpdate {
  display_name?: string;
  language_preference?: "en" | "ar";          // NEW
}
```

Mirrored on the backend in `services/api/app/models/profile.py`:

```python
class ProfileUpdate(BaseModel):
    display_name: str | None = None
    language_preference: Literal["en", "ar"] | None = None   # NEW

class ProfileResponse(BaseModel):
    # ...existing fields unchanged...
    language_preference: str | None = None                    # NEW
```

## Entity: Message Catalog (Supabase Storage, not a DB table)

One JSON object per locale, keyed by translation key (nested namespaces per screen/domain, e.g.
`search.emptyState`, `bookings.confirmed`). Not a relational entity — a versioned content artifact,
per `research.md` R3.

| Field (within the JSON metadata wrapper) | Type | Notes |
|---|---|---|
| `locale` | `"en" \| "ar"` | Matches `Locale` above |
| `version` | string (timestamp or hash) | Used to detect staleness in the in-memory cache and force a refresh |
| `messages` | nested object | The actual key → translated string tree consumed by `next-intl` |

**Completeness/fallback rule** (FR-011): when a key exists in `en.json` but not yet in `ar.json`, the
loader falls back to the English string for that specific key rather than rendering blank or a raw
key — this is `next-intl`'s built-in behavior when a fallback message set is provided, not a custom
mechanism.

## Entity: `_NOTIFICATION_TEMPLATES` (in-code, `fcm_service.py`)

Not persisted — a Python module-level constant, restructured per `research.md` R6:

```python
_NOTIFICATION_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "booking_received": {
        "en": ("New Booking Request", "A passenger wants to join your ride."),
        "ar": ("طلب حجز جديد", "يريد أحد الركاب الانضمام إلى رحلتك."),
    },
    # ...one entry per existing event_type, both locales...
}
```

`send_push_notifications()` looks up the recipient's `language_preference` (defaulting to `"en"` when
`NULL`) to select the inner dict before formatting the `messaging.Notification`.

## Relationships

```
profiles (1) ──── language_preference (column, nullable) ──── drives ────► Locale resolution
                                                                             (middleware.ts)
Locale ──── selects ────► Message Catalog entry (Supabase Storage)
Locale ──── selects ────► _NOTIFICATION_TEMPLATES[event_type][locale] (fcm_service.py)
```

No new foreign keys, no new join tables — this feature adds one nullable column to an existing table
and two content artifacts (message catalog, notification templates) that are *selected by* that
column's resolved value, not related to it via SQL joins.
