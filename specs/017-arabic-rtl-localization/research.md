# Phase 0 Research: Arabic & RTL Localization

No `[NEEDS CLARIFICATION]` markers remained in the spec after `/speckit-clarify`, so this research
phase resolves *implementation-approach* unknowns rather than product-scope unknowns — the questions
a Technical Context can't leave open going into design.

## R1: i18n library for Next.js 14 App Router

**Decision**: `next-intl`.

**Rationale**: `apps/main` uses the Next.js 14 App Router with a server/client component split
(`middleware.ts` for SSR auth checks, `"use client"` components like `ProfileEditor.tsx` for
interactivity). `next-intl` is built specifically for this split — it provides server-side message
resolution (`getMessages()`/`getTranslations()`) for Server Components and a
`NextIntlClientProvider` + `useTranslations()` hook for Client Components, without requiring a data
fetching library or a rewrite of existing components' rendering model. It also supports ICU message
syntax, which covers pluralization/formatting needs (e.g., "1 rating" vs "N ratings", already a
manual ternary in `RatingSummary` today) without extra tooling. It is also the option already named
in the roadmap's Phase 14 deliverables note.

**Alternatives considered**:
- `react-i18next` — mature and framework-agnostic, but its App Router integration requires more
  manual plumbing (no built-in Server Component message-loading story) for no added benefit here.
- Hand-rolled context + JSON lookup — avoids a dependency, but reimplements ICU pluralization,
  fallback-on-missing-key (FR-011), and SSR/CSR message hydration that `next-intl` already solves;
  not justified for a two-locale, single-app scope.

## R2: Locale routing — URL-prefixed vs cookie-resolved

**Decision**: No `[locale]` URL segment. Locale is resolved server-side from (in priority order) an
authenticated user's `profiles.language_preference`, then a `NEXT_LOCALE` cookie for
unauthenticated/no-preference visitors, then the spec's default (Arabic, per spec Assumptions).
`next-intl` is configured with `localePrefix: 'never'`.

**Rationale**: `apps/main`'s existing route structure (`(app)`, `(auth)`, `(driver)`,
`(onboarding)`, `(passenger)` route groups, plus dynamic segments like `/rides/[id]`) has no locale
segment today, and `middleware.ts` already does path-based logic (`PUBLIC_PATHS`,
`PASSENGER_VERIFIED_PREFIXES`) keyed on the current unprefixed paths. Introducing `/en/...` and
`/ar/...` would require rewriting every existing route matcher, every internal link, and the
verification-gating logic in `middleware.ts` for zero product value the spec asks for (FR-002 asks
for an in-place toggle, not a URL change) — this would be exactly the kind of unnecessary complexity
the constitution's Quality Standards ask to avoid. Cookie/profile-resolved locale keeps every
existing route, guard, and link untouched.

**Alternatives considered**:
- Prefixed routing (`/en`, `/ar`) — `next-intl`'s more common/default setup, better for SEO of
  fully public marketing sites, but `apps/main` is an authenticated app behind `middleware.ts`
  auth gating, not an SEO-indexed public site — the benefit doesn't apply here and the migration
  cost is real.

## R3: Message catalog storage & the no-redeploy requirement (NFR-003)

**Decision**: Canonical English (`messages/en.json`) ships in the repo/build as the fallback source
(FR-011) and as the editable source of truth for translators. At runtime, `apps/main` loads the
active message catalog per locale from a Supabase Storage bucket, cached in-process with a periodic
background refresh — the same "singleton config cached in-process, refreshed on an interval" shape
`services/api` already uses for `pricing_config`/`ranking_config` and the continuous-learning
pipeline's config table (see `specs/016-continuous-learning-pipeline/plan.md`). Publishing an updated
`ar.json` to Storage takes effect on the next cache refresh, with no rebuild/redeploy.

**Rationale**: NFR-003 explicitly requires copy-only updates without a full redeploy, "to keep
translation quality maintainable over time" (spec). Bundling JSON catalogs at build time (the default
`next-intl` setup) would fail that requirement outright — every wording fix would need a full
`apps/main` build + deploy cycle. Runtime-loading from Storage, with an in-memory cache to avoid a
Storage round-trip per request, reuses a pattern this codebase already has in production rather than
introducing a new one (e.g., a CMS or translation-management service), which would be disproportionate
for two locales and one app.

**Alternatives considered**:
- Build-time bundled JSON (default `next-intl`) — simplest, but fails NFR-003.
- Third-party translation-management SaaS (e.g., Lokalise, Crowdin) — solves the same problem with a
  nicer translator UI, but adds an external dependency/cost not justified for a two-locale MVP; can be
  revisited later without changing the runtime-loading architecture.

## R4: RTL layout mechanism

**Decision**: Set `dir="rtl"` / `dir="ltr"` on `<html>` in `apps/main/src/app/layout.tsx` based on
resolved locale, and rely on Tailwind CSS's built-in `rtl:`/`ltr:` variants (available in the
installed `tailwindcss@^3.4.1`, no plugin) across `packages/ui` components and `apps/main` screens
wherever a class currently encodes a physical direction (e.g., `ml-2`, `text-left`,
`border-l`) that should instead flip in RTL. Directional icons (back/forward arrows, e.g. the `←` in
`ProfileEditor.tsx`) get RTL-aware equivalents.

**Rationale**: Tailwind's `[dir]`-attribute-based `rtl:`/`ltr:` variants require no new dependency and
compose with the project's existing token-based Tailwind config (`brand.*`, `surface.*`, etc. in
`apps/main/tailwind.config.ts`) — this is a class-level audit, not an architectural change.

**Alternatives considered**:
- `tailwindcss-rtl` / logical-properties plugin — redundant with Tailwind 3.3+'s native `rtl:`/`ltr:`
  variants; adding it would be an unjustified extra dependency.
- CSS logical properties everywhere (`margin-inline-start` etc. via arbitrary Tailwind values) —
  more "correct" in the abstract, but a much larger diff across `packages/ui` for no behavior
  difference from the native variants; not justified for two supported directions.

## R5: One-time language prompt for existing users (FR-013)

**Decision**: `language_preference` is a nullable column; `NULL` means "no explicit choice yet." A
`LanguagePromptModal` client component checks the current user's `language_preference` on first
render after this feature ships and, if `NULL`, shows a dismissible-only-by-choosing modal ("Choose
your language / اختر لغتك") that calls the same profile-update endpoint as the Settings toggle. It is
non-blocking (does not gate route access the way `middleware.ts`'s verification-status check does) —
choosing a language is a preference, not an eligibility gate, so it must not lock existing users out
of the app the way `/onboarding/verify-id` does for unverified passengers.

**Rationale**: FR-013 requires the prompt but the spec's Business Objective is to *remove* friction,
so gating navigation on a language choice would contradict that intent. A modal that stays open until
answered — but doesn't block the URL/route the user landed on — satisfies "must present a one-time
prompt" without inventing a new blocking-gate mechanism duplicate of the existing verification gate.

**Alternatives considered**:
- Redirect to a dedicated `/choose-language` route via `middleware.ts` (mirroring the
  `/onboarding/verify-id` pattern) — rejected: conflates a soft preference with a hard eligibility
  gate, and would block deep links (e.g., a notification linking straight to a ride) for existing
  users on their very next login, which is a worse experience than the feature is meant to fix.

## R6: FCM notification template localization (FR-008)

**Decision**: `_NOTIFICATION_TEMPLATES` in `services/api/app/services/fcm_service.py` changes shape
from `dict[str, tuple[str, str]]` to `dict[str, dict[str, tuple[str, str]]]` (event_type → locale →
`(title, body)`). `send_push_notifications()` fetches the recipient's `profiles.language_preference`
(already has the `recipient_user_id`) in the same query pattern it already uses to fetch device
tokens, and falls back to `'en'` when the stored value is `NULL` — consistent with FR-011's
fallback-to-English principle applied to notification content as well as UI strings.

**Rationale**: This is a minimal, additive change to an existing, already-centralized template dict —
no new notification infrastructure, no per-notification-type special casing.

**Alternatives considered**: Move templates into the same Storage-backed message catalog as the UI
strings (R3) — considered for consistency, but rejected for this iteration: FCM templates are a small,
fixed set (~12 event types) directly coupled to backend event-emission code, not requestable content
a translator needs to iterate on independently of a deploy; keeping them as a Python dict next to the
send logic is simpler and matches the existing pattern in this file.

## R7: Locale-aware date/currency formatting (FR-007)

**Decision**: Extend the existing `formatDate(isoString: string)` in `packages/shared/src/utils/index.ts`
to `formatDate(isoString: string, locale: "en" | "ar" = "en")`, mapping to `Intl.DateTimeFormat` with
`"en-EG"`/`"ar-EG"`. Add a new `formatCurrency(amount: number, locale: "en" | "ar" = "en")` using
`Intl.NumberFormat` with `currency: "EGP"`, and per spec Technical Considerations, force
`numberingSystem: "latn"` for both locales so numerals stay Western Arabic digits even under `ar-EG`
(which would otherwise default to Eastern Arabic numerals). The ~16 call sites currently doing ad hoc
`toLocaleString`/`Intl.*` calls migrate onto these two shared functions.

**Rationale**: `packages/shared/src/utils/index.ts` already exists as the shared formatting home with
exactly one function (`formatDate`) hardcoded to `"en-EG"` — parameterizing it is the smallest change
that satisfies FR-007, and consolidating the ~16 inline call sites removes duplication that would
otherwise need to be fixed in 16 places for the numeral-system requirement alone.

**Alternatives considered**: Let `next-intl`'s built-in `useFormatter()` handle all date/currency
formatting instead of the shared utility — viable for Client Components, but several of the 16 call
sites format inside server-rendered/data-fetching code paths (e.g., API response shaping) where
`next-intl`'s formatter hook isn't available; keeping one plain-function formatter usable from both
contexts avoids a split implementation.

---

**Output check**: All unknowns identified for Technical Context are resolved above; no
`NEEDS CLARIFICATION` markers remain in `plan.md`.
