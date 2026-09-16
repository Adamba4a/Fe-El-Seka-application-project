# Localization audit — 2026-09-16

## Verified and fixed
- Main app has next-intl catalogs, locale cookie/profile preference, and root html lang/dir; default locale is Arabic.
- Both catalogs contain 1,049 leaf keys after this feature; no missing English or Arabic keys.
- All visible support labels, validation, errors, success and launcher text are translated. The hidden bot-trap label is not user-facing.
- Support renders at the root provider, outside login, onboarding and authenticated route groups. It requires no user token. A language switch inside the dialog makes language choice reachable during signup screens without their own switch.
- Fixed the message loader: offline/missing remote Arabic catalogs and newly introduced keys now fall back to bundled Arabic, rather than bundled English. Remote catalog overrides still work.
- Replaced two hardcoded Premium Pickup/Dropoff labels on passenger ride details with existing translation keys.
- Mobile browser checks at 390×844 verified RTL/LTR, email direction, localized feedback, dialog bounds, switching locale, draft preservation and Escape/focus restoration. Screenshots: support-ar.png and support-en.png.

## Remaining separate work
- The existing admin app is English-only (navigation, pages, no next-intl provider). The support inbox follows its current language. Full admin bilingual conversion needs a separate scoped task/spec; the user-facing support feature is bilingual.
- Main middleware's maintenance HTML is English-only and replaces the whole app while maintenance mode is active, including support. This feature covers normal signup/in-app operation, not offline support during maintenance.
- Some existing authentication screens surface raw provider error strings (for example OTP session errors), which can be English in Arabic mode. Translate provider error codes in an authentication follow-up.
- Catalog parity and source scans do not prove every runtime state is localized. Authenticated driver/passenger journeys were not browser-tested with real accounts during this change.

## Repeatable checks
Run `node specs/032-contact-support/catalog-check.cjs` from repository root. Browser check instructions are in quickstart.md.
