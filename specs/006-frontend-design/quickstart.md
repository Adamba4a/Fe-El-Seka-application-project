# Quickstart: Frontend Design System & Screen Library

**Feature**: `006-frontend-design` | **Date**: 2026-06-20

This guide describes how to validate that all screens and components introduced in this phase are correctly implemented. Run these steps after implementation is complete.

---

## Prerequisites

- Docker Desktop running
- `pnpm` installed
- Supabase local instance running (via `supabase start` or the Docker Compose stack from `005-dockerization`)
- A test driver account that has been verified and has an approved vehicle
- A test passenger account that has been verified

---

## 1. Start the Development Environment

```bash
# From repo root
docker compose up
```

The main app is available at `http://localhost:3000`.

---

## 2. Build Quality Gate (run first)

```bash
pnpm --filter main build
```

**Expected**: Exits with code 0. Zero TypeScript errors. Zero TypeScript warnings.

If this fails, stop — do not proceed with visual validation until the build passes.

---

## 3. Token Validation (grep check)

```bash
grep -rE '(#[0-9a-fA-F]{3,6}|text-(gray|blue|red|green|yellow|amber|orange|purple)-[0-9]+|bg-(gray|blue|red|green|yellow|amber|orange|purple)-[0-9]+)' apps/main/src/components apps/main/src/app
```

**Expected**: Zero matches. Any match is a hardcoded color violation (FR-004).

---

## 4. Auth & Verification Screens

Navigate to `http://localhost:3000` as an unauthenticated user.

| Screen | URL | What to verify |
|---|---|---|
| Phone entry (login) | `/login` | Brand colors; styled input; country code or phone field; primary button |
| OTP verification | `/otp` | Segmented input (one box per digit); countdown timer; resend button disabled initially; auto-advance on digit entry; paste an OTP string → all boxes fill |
| Profile setup | `/onboarding/profile` | Name input; circular photo upload preview on image select |
| Role selection | `/role-select` | Driver and passenger as card components (not radio buttons); icons + descriptions |
| Passenger ID upload | `/onboarding/verify-id` | Thumbnail preview on file select; confirm button disabled until file selected |
| Driver ID upload | `/onboarding/driver/verify-documents` | Thumbnail preview; confirm button gating |
| Vehicle registration | `/onboarding/driver/register-vehicle` | Form with token-based styling; no hardcoded colors |
| Verification status — pending | (after submission) | Neutral waiting illustration; no CTA |
| Verification status — approved (driver) | (admin approves in test) | Success illustration; "Go to my rides" CTA → navigates to `/rides` |
| Verification status — approved (passenger) | (admin approves in test) | Success illustration; "Find a ride" CTA → navigates to `/search` |
| Verification status — rejected | (admin rejects in test) | Error prompt; "Resubmit" action visible |

**For all screens**: Resize browser to 375px width. Verify no horizontal overflow. Verify all buttons and inputs are at least 44×44px tap target.

---

## 5. Ride Management Screens

Log in as the verified driver.

| Screen | URL | What to verify |
|---|---|---|
| Ride dashboard — empty | `/rides` (no rides yet) | Illustration shown; "Post your first ride" button navigates to `/rides/new` |
| Ride dashboard — with rides | `/rides` (after creating one) | Each ride renders as `RideCard`; status badge visible; no overflow at 375px |
| Create ride | `/rides/new` | Full-screen map background; `BottomSheet` slides up from bottom; panel ≤65% viewport height; drag handle collapses it; form inside panel; map tile loads within 3s |
| Create ride — pin origin/destination | `/rides/new` | Address labels appear in panel after map pin drop |
| Create ride — submit | `/rides/new` | Button shows spinner while pending; inline error appears on failure |
| Ride detail | `/rides/:id` | `RideStatusBadge` present; `RideHistoryLog` shows entries newest-first; `StartCompleteActions` shows "Start Ride" for scheduled rides |
| Edit ride | `/rides/:id/edit` | Dirty-field indicator visible when a field is changed; tokens throughout |
| Cancel ride | `/rides/:id` (tap "Cancel") | `BottomSheet` slides up; confirm button disabled until reason entered; submits from sheet, no navigation |

---

## 6. Component Library Spot-Check

Open the browser console and run these checks on any page that imports components:

```
// Verify BottomSheet is importable
import('@/components').then(m => console.log(Object.keys(m)))
// Expected output includes: BottomSheet, RideCard, RideStatusBadge, RideHistoryLog, StartCompleteActions
```

Alternatively, create a temporary test page at `apps/main/src/app/test-components/page.tsx`, render all five components with minimal props, and confirm no runtime errors.

---

## 7. Animation Performance Check

On the Create Ride screen:
1. Open Chrome DevTools → Performance tab.
2. Start a recording.
3. Tap the drag handle to open and close the `BottomSheet` twice.
4. Stop recording.
5. Verify: `BottomSheet` animation frames are in the **Compositor** thread (green bars in the flame chart), not the **Main** thread. This confirms CSS `transform` is GPU-accelerated.
6. Verify: total open or close animation duration is ≤300ms.

---

## 8. CLS Check (Cumulative Layout Shift)

On any screen, open Chrome DevTools → Lighthouse tab:
1. Set device to **Mobile**.
2. Run a Lighthouse audit.
3. Verify **CLS score ≤ 0.1** on each screen.

Alternatively, use the Web Vitals extension to measure CLS in real-time during navigation.

---

## Done When

- [ ] `pnpm --filter main build` exits 0 with zero TypeScript errors
- [ ] Token grep returns zero matches
- [ ] All 13 screens render correctly at 375px with no horizontal overflow
- [ ] `BottomSheet` open/close animation is ≤300ms and runs on the compositor thread
- [ ] All 5 components importable from `@/components` and render with minimum props
- [ ] Verification status approved screen shows correct role-aware CTA
- [ ] Empty ride dashboard shows illustration + "Post your first ride" button
- [ ] OTP auto-advance and paste-to-fill work correctly
