# Implementation Plan: Arabic & RTL Localization

**Branch**: `017-arabic-rtl-localization` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-arabic-rtl-localization/spec.md`

## Summary

Give `apps/main` (Passenger + Driver) a full Arabic display language with correct RTL layout,
alongside the existing English experience, switchable at any time via a visible toggle. The design
deliberately reuses existing infrastructure rather than introducing a parallel system: `next-intl`
supplies message resolution and pluralization on top of the existing Next.js 14 App Router without
requiring a `[locale]` URL-segment rewrite (locale is resolved from a cookie plus the existing
`profiles` row, not the path, so none of the current route groups — `(app)`, `(auth)`, `(driver)`,
`(onboarding)`, `(passenger)` — need to move); RTL is achieved with Tailwind's built-in `rtl:`/`ltr:`
variants and a `dir` attribute on `<html>`, not a new CSS framework; message catalogs are loaded at
runtime from Supabase Storage with an in-memory cache, mirroring the existing `pricing_config` /
`ranking_config` runtime-refreshable-config pattern already used in `services/api`, so copy-only
changes need no redeploy (NFR-003); and FCM push localization extends the existing
`_NOTIFICATION_TEMPLATES` dict in `fcm_service.py` from a flat `{event_type: (title, body)}` map to a
per-language map, keyed off a new nullable `profiles.language_preference` column. The Admin Panel
(`apps/admin`) and OTP SMS delivery are explicitly untouched, per spec Out-of-Scope/FR-014.

## Technical Context

**Language/Version**: TypeScript (Next.js 14.2.3, React 18) for `apps/main`; Python 3.11 for the
small `services/api` surface touched (profile field + FCM template lookup) — both match existing
versions in use, no upgrades.

**Primary Dependencies**: `next-intl` (NEW — App Router-native i18n, ICU message format, ships a
`NextIntlClientProvider` and `useTranslations` hook that fit the existing client/server component
split) added to `apps/main`. No new dependencies in `services/api`, `services/ai`, or `packages/ui` —
RTL styling uses Tailwind CSS's built-in `rtl:`/`ltr:` variants (already available in the installed
`tailwindcss@^3.4.1`, no plugin needed).

**Storage**: Supabase Postgres — one new nullable column on the existing `profiles` table
(`language_preference`). Supabase Storage — one new bucket (or a new prefix in an existing
config-style bucket) holding a JSON message catalog per locale (`en.json`, `ar.json`), loaded at
request time and cached in-process with periodic refresh, the same shape as the existing
`model-registry` / continuous-learning config artifacts.

**Testing**: `apps/main` currently has no frontend automated test framework configured (no
jest/vitest/playwright present) — manual verification via `quickstart.md` is the existing convention
for this app, continued here. `services/api` changes (profile field, FCM template lookup) get
`pytest` unit tests under `services/api/tests/unit`, matching the existing convention.

**Target Platform**: Same Linux/Docker deployment already in place for `apps/main` and `services/api`
on Bunny (per `project_online_deployment_migration`) — no new runtime or infrastructure.

**Project Type**: Monorepo, frontend-led with a small backend extension — primarily `apps/main`
(+ shared `packages/ui`, `packages/shared`), plus two small, targeted changes in `services/api`
(profile field, FCM template selection). `apps/admin` is untouched (spec Out-of-Scope).

**Performance Goals**: Language switch re-renders the current screen in <2s (NFR-001); translated
content adds <10% to baseline screen load time (NFR-002) — message catalogs are small (~KBs of JSON)
and cached in-process after first load, so this is expected to be well within budget.

**Constraints**: No `[locale]` URL segment — all existing routes and links keep their current paths.
No changes to `apps/admin`. No changes to OTP/auth SMS content (FR-014). `middleware.ts` already
queries `profiles` per-request for verification-status gating on passenger routes; locale resolution
is added to that same code path rather than a second per-request query, to avoid doubling
request-path latency. Route/map content (OSRM/PostGIS-derived) is never mirrored, per Principle II
and spec Technical Considerations.

**Scale/Scope**: 2 locales (English, Arabic) across all Passenger + Driver screens in `apps/main`;
~12 known FCM notification event types (`fcm_service.py`) need per-locale template pairs; ~16 known
call sites currently doing ad hoc `toLocaleString`/`Intl.*` formatting need to move onto a shared,
locale-aware formatter. Exact per-screen string inventory is a `/speckit-tasks` concern, not fixed
here.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Driver-First Route Sharing | Not affected — this feature changes display language/layout only, not the ride-creation/discovery model. | PASS (N/A) |
| II. Route Intelligence Over Geographic Proximity | Preserved explicitly: map/route content stays sourced from OSRM/PostGIS and is never mirrored or re-derived for RTL display (spec Technical Considerations, FR-003 map exemption). | PASS |
| III. Trust Before Transportation | Not weakened — verification-status gating in `middleware.ts` is untouched; OTP identity-verification SMS content is explicitly left as-is (FR-014) so no verification-flow behavior changes. | PASS (N/A) |
| IV. AI-Augmented Transportation | Not affected — no AI/matching/ranking/pricing logic changes. | PASS (N/A) |
| V. Mobile-First User Experience | Directly serves this principle — this feature exists to remove the English-only friction blocking the platform's primary Arabic-speaking market from a simple, confident mobile experience. | PASS |
| VI. Modular Domain-Driven Architecture | Localization is itself a bounded capability (spec Constitutional Domain) that touches other domains' *display text only*, not their business logic — `profile_service.update_profile()` gains one field, `fcm_service.py` gains per-locale lookup, no domain's business rules move or duplicate. Cross-domain touch points are enumerated in spec Dependencies. | PASS |
| VII. Shared Foundations, Independent Applications | Directly serves this principle — RTL/i18n plumbing (locale resolution, message provider, formatter) is built once in `packages/ui` / `packages/shared` and consumed by both Passenger and Driver views inside `apps/main`; `apps/admin` remains fully independent and untouched. | PASS |

No violations requiring Complexity Tracking. The feature's size (touches most screens in `apps/main`)
is inherent to "full Arabic UI" as scoped by the spec, not an architectural complexity choice.

## Project Structure

### Documentation (this feature)

```text
specs/017-arabic-rtl-localization/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── profile-language-preference.md
│   ├── notification-localization.md
│   └── message-catalog.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
supabase/migrations/
└── 20260805000001_phase14_language_preference.sql   # NEW — profiles.language_preference column

apps/main/
├── src/
│   ├── middleware.ts                        # EXTENDED — resolve locale (cookie + profiles.language_preference,
│   │                                         #   read in the same query used today for verification_status) and
│   │                                         #   set the NEXT_LOCALE cookie / request header for next-intl
│   ├── app/
│   │   ├── layout.tsx                       # EXTENDED — <html lang={locale} dir={ltr|rtl}>, wrap children in
│   │   │                                     #   NextIntlClientProvider
│   │   └── (app)/settings/profile/
│   │       ├── ProfileEditor.tsx            # EXTENDED — add a LanguageSection (toggle), calls updateMe() with
│   │       │                                #   language_preference
│   │       └── LanguagePromptModal.tsx      # NEW — one-time modal for existing users with
│   │                                        #   language_preference = NULL (FR-013), rendered from a shared layout
│   │                                        #   slot so it can appear on first post-launch page view, not just Settings
│   ├── lib/
│   │   ├── i18n/
│   │   │   ├── config.ts                    # NEW — supported locales, default locale, cookie name
│   │   │   ├── request.ts                   # NEW — next-intl server config: resolves locale, loads messages via
│   │   │   │                                #   getMessages() (Supabase Storage-backed, see research.md R3)
│   │   │   └── messages-loader.ts           # NEW — fetch + in-memory cache + periodic refresh of the JSON message
│   │   │                                    #   catalog per locale (mirrors services/api's config-cache pattern)
│   │   └── api/profiles.ts                  # EXTENDED — updateMe() accepts language_preference
├── messages/
│   ├── en.json                              # NEW — canonical English source strings (also the FR-011 fallback)
│   └── ar.json                              # NEW — Arabic translations
└── package.json                             # EXTENDED — add next-intl dependency

packages/ui/src/
└── components/                              # EXTENDED — audit for RTL: replace any remaining physical
                                              #   left/right Tailwind classes with logical rtl:/ltr: variants so
                                              #   the shared library mirrors correctly by default

packages/shared/src/
├── types/user.ts                            # EXTENDED — Profile / ProfileUpdate gain language_preference
└── utils/index.ts                           # EXTENDED — formatDate(iso, locale) takes a locale param instead of
                                              #   a hardcoded "en-EG"; NEW formatCurrency(amount, locale) for EGP

services/api/app/
├── models/profile.py                        # EXTENDED — ProfileUpdate/ProfileResponse gain language_preference
├── services/
│   ├── profile_service.py                   # EXTENDED — update_profile() accepts language_preference
│   └── fcm_service.py                       # EXTENDED — _NOTIFICATION_TEMPLATES becomes
│                                             #   {event_type: {locale: (title, body)}}; send_push_notifications()
│                                             #   looks up the recipient's profiles.language_preference
│                                             #   (fallback 'en' when NULL, per FR-011's fallback principle)
├── api/profiles/router.py                   # EXTENDED — PUT /profiles/me passes language_preference through
└── tests/unit/
    └── test_fcm_service.py                  # NEW/EXTENDED — per-locale template selection + NULL-fallback tests
```

**Structure Decision**: Monorepo, frontend-led extension of `apps/main` (with shared-package
plumbing in `packages/ui`/`packages/shared`) plus a narrowly-scoped `services/api` extension for the
one new profile field and per-locale FCM templates. No new top-level app or service. `apps/admin` is
untouched; `services/ai` is untouched.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
