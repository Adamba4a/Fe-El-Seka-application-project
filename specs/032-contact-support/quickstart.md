# Contact Support — verification and rollout

## Before deployment
1. Apply `supabase/migrations/20260916000001_contact_support.sql` through the existing migration process, before deploying the API. The migration adds private tables; do not grant browser roles read access.
2. Deploy the API and both main/admin apps together. The recipient defaults to `triplyy.info@gmail.com`; `SUPPORT_EMAIL` overrides it if explicitly configured.
3. Use the existing Resend setup and verified `noreply@triplyy.net` sender. With no real Resend key the existing transport uses local Mailpit instead of external email. Do not use a Gmail password. No credentials were added by this feature.
4. Configure trusted proxy addresses correctly in the API deployment. Rate limiting uses `request.client.host`; an unconfigured proxy can make all users share one quota. Do not trust arbitrary client-supplied forwarding headers.
5. Verify a test report with an address you control. Check that it appears under admin `/support`, the notification reaches the inbox, and its delivery state becomes sent. The poll interval is 60 seconds. No confirmation email is sent to the submitted contact.
6. In a staging database test simultaneous same-ID submissions and email/IP quotas; verify browser anon/authenticated roles cannot query either support table. Test admin status history and delivery recovery after restart. These need a live database and were not executed locally.

## Completed checks
- Backend: 28 tests passed (24 support/transport tests plus 4 existing exception-handler regressions).
- Python lint passed for support model/router/service/tests.
- TypeScript checks passed for main and admin.
- Targeted ESLint passed for support widget, root layout, message loader, admin inbox and admin navigation.
- Catalog test passed: key parity, both locales offline, Arabic remote catalog absent, new keys absent from remote catalog, and remote override preservation.
- Headless Edge at 390×844 passed: Arabic/English dialog, validation, failed submission draft, Escape/focus restoration, retry ID reuse, success, locale switch, throttling message. Network support submissions were intercepted; no real report/email was sent.
- `git diff --check` passed.

## Commands
From `services/api`, run `.venv/Scripts/python.exe -m pytest tests/unit/test_support.py tests/unit/test_main_exception_handlers.py -q`.

From the repository root, run `pnpm --filter @fe-el-seka/main typecheck`, `pnpm --filter @fe-el-seka/admin typecheck`, and `node specs/032-contact-support/catalog-check.cjs`.

For the browser check, start the main app at http://localhost:3000 and run `node specs/032-contact-support/browser-check.cjs` with Playwright installed (or set `PLAYWRIGHT_MODULE` to an installed module). It uses installed Edge, mocks every support submission, and writes two screenshots alongside this document.

## Delivery and operational limits
Saved reports survive email failures. Retries wait 1 minute, 5 minutes, 30 minutes, then 2 hours; the fifth failure marks the email failed. Admins can still read the report and contact its supplied address. Delivery is at-least-once: a process crash after provider acceptance but before commit can produce a duplicate email. Rate limits are basic abuse protection, not a substitute for edge-level bot protection at higher traffic.

The local Docker daemon was unavailable. No migration was applied, no production services were deployed, and actual inbox delivery is unverified. See localization-audit.md for existing app-wide gaps.
