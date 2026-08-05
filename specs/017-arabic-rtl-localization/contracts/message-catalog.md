# Contract: UI Message Catalog

Governs the runtime-loaded translation content consumed by `next-intl` in `apps/main`. Not a public
API — an internal content contract between the translation-maintenance process and the app's message
loader (`apps/main/src/lib/i18n/messages-loader.ts`).

## Storage format

One JSON object per locale, stored in Supabase Storage:

```
{bucket}/messages/en.json
{bucket}/messages/ar.json
```

```json
{
  "locale": "ar",
  "version": "2026-08-05T12:00:00Z",
  "messages": {
    "search": {
      "emptyState": "لا توجد رحلات مطابقة حالياً",
      "filterLabel": "تصفية النتائج"
    },
    "bookings": {
      "confirmed": "تم تأكيد الحجز!"
    }
  }
}
```

- `messages` is a nested object matching `next-intl`'s namespace convention (top-level keys are
  screen/domain namespaces, e.g. `search`, `bookings`, `settings`) — mirrors the existing route-group
  organization of `apps/main/src/app` for discoverability, but is not required to match it 1:1.
- `version` MUST change on every published update (a fresh ISO timestamp is sufficient) — the loader
  uses it to detect a stale in-memory cache entry without re-parsing unchanged JSON on every refresh
  tick.

## Loader contract (`messages-loader.ts`)

- On cold start: fetch both `en.json` and `ar.json` from Storage; if either fetch fails, fall back to
  the repo-bundled `apps/main/messages/en.json` for **both** locales (never fail to render — an
  Arabic-speaking user seeing English due to a Storage outage is degraded, not broken; this is a
  stricter application of the same FR-011 fallback principle already required for missing keys).
- Background refresh: re-fetch on an interval (proposed: every 5 minutes, tunable) and swap the cache
  only if `version` changed — matches the "cached in-process, refreshed on an interval" shape of
  `services/api`'s `pricing_config`/`ranking_config` (see `research.md` R3), applied client-side here
  since `apps/main` doesn't have a long-lived process to run a background loop in the same way.
- Per-request cost: zero additional network calls — `next-intl`'s server config
  (`apps/main/src/lib/i18n/request.ts`) reads from the already-warm in-memory cache, never fetches
  Storage inline in the request path.

## Key-completeness contract (FR-011)

- `en.json` is the canonical key set — every key that exists anywhere in the app MUST exist in
  `en.json`.
- `ar.json` MAY lag behind `en.json` (translation-in-progress is expected, per spec Edge Cases). Any
  key present in `en.json` but absent from `ar.json` renders the English string when the active
  locale is Arabic — never a blank string, never a raw key like `search.emptyState`.
- The inverse (a key in `ar.json` but not `en.json`) is invalid and MUST be caught before publishing —
  it would mean English (the fallback and default reviewable source) is missing content that Arabic
  has, breaking FR-011 for English-selected users. Not runtime-enforced in this iteration; treated as
  a publish-time linting step outside this feature's scope (see `plan.md` — `/speckit-tasks` may
  choose to add a simple key-diff script, but it isn't a functional requirement).

## Explicitly out of contract

- FCM push notification content — separate contract (`notification-localization.md`); not sourced
  from this catalog.
- User-generated content — never passes through this catalog (FR-009).
