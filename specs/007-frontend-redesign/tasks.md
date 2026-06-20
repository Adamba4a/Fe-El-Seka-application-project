# Frontend Redesign Tasks

**Status**: PENDING — do not start until passenger API experience is complete
**Reference designs**: `C:\Users\ADAM\AppData\Local\Temp\screen (2).png` (passenger) and `screen (3).png` (driver)
**Scope**: Visual overhaul only — routing, auth, API integration, and middleware are unchanged

---

## Design System Reference

Extracted from the Stitch mobile designs:

| Token | Value | Usage |
|---|---|---|
| Brand primary (navy) | `#1B2D5B` | Headings, "Join Ride" buttons, earnings card bg, passenger active nav icon |
| Accent (orange) | `#E8841A` | "GOOD MORNING" label, "View all" links, driver active nav, FAB, time labels, PENDING badge, "2 scheduled rides" highlight |
| Surface background | `#EEF2F7` | Page background (light blue-gray) |
| Surface card | `#FFFFFF` | All cards |
| CONFIRMED badge | `#16A34A` text + light green bg | Trip status |
| PENDING badge | `#E8841A` text + orange border | Trip status |
| UPCOMING badge | `#16A34A` text + green border | Joined ride status |
| Rating star | `#E8841A` | Driver/ride ratings |

Typography:
- Section label above greeting: small-caps orange, e.g. "GOOD MORNING"
- Main greeting: very large bold dark navy, e.g. "Welcome back, Sarah" / "Ahlan, Ahmed!"
- Route display: bold dark navy with `→` arrow, e.g. "Maadi → Smart Village"
- Time/date sub-label: orange, e.g. "TODAY • 04:30 PM"

---

## Phase 1 — Design Tokens

- [ ] T001 Update `apps/main/src/app/globals.css` — replace current color tokens with new palette:
  - `--color-brand-primary: #1B2D5B` (navy)
  - `--color-brand-accent: #E8841A` (orange)
  - `--color-surface-bg: #EEF2F7`
  - Keep all existing token names where they map cleanly; add `--color-brand-accent` as a new token
- [ ] T002 Update `apps/main/tailwind.config.ts` — add `accent` key under `brand` and verify all existing token mappings still resolve
- [ ] T003 Update `specs/006-frontend-design/data-model.md` — append new token rows for `brand-accent`, `brand-accent-hover`

---

## Phase 2 — Shared Shell Components

- [ ] T004 Rewrite `apps/main/src/components/layout/TopBar.tsx` (or create it if it doesn't exist):
  - **Passenger variant**: "Fe El Seka" text logo (left) + bell icon + avatar with green-bordered circle (right)
  - **Driver variant**: avatar + name + green "● VERIFIED DRIVER" pill (left) + bell + settings gear (right)
  - Props: `variant: 'passenger' | 'driver'`, `userName`, `avatarUrl`, `notificationCount?`

- [ ] T005 Rewrite bottom navigation for both roles:
  - **Passenger** (`apps/main/src/app/(passenger)/layout.tsx`): Dashboard | Find a Ride | My Trips | Profile — active tab uses navy icon
  - **Driver** (`apps/main/src/app/(driver)/layout.tsx`): Dashboard | My Rides | Earnings | Profile — active tab uses orange icon
  - Active tab indicator: filled icon, no background pill — just color change

---

## Phase 3 — Driver Dashboard

Reference: `screen (3).png`

- [ ] T006 Create `apps/main/src/components/driver/StatsCard.tsx`:
  - Dark navy variant (Earnings): label "EARNINGS", large "EGP X,XXX", green "↗ +X% this week"
  - White variant (Rides): label "RIDES", large number, sub-label "Total completed"
  - Cards are horizontally scrollable (there is a third card partially visible — add Rating card with star)

- [ ] T007 Create `apps/main/src/components/driver/UpcomingTripCard.tsx`:
  - Orange time label: "TODAY • 04:30 PM" or "TOMORROW • 08:00 AM"
  - Status badge top-right: CONFIRMED (green) or PENDING (N) (orange)
  - Route: "Origin → Destination" in bold large navy text
  - Passenger avatars row (stacked circles) + "+N" overflow
  - "EGP XX / Estimated Payout" (right-aligned)
  - "Waiting for N more..." when PENDING

- [ ] T008 Rebuild `apps/main/src/app/(driver)/dashboard/page.tsx`:
  - TopBar (driver variant)
  - Greeting: "Ahlan, [name]!" + "You have **N scheduled rides** today." (bold orange for count)
  - Horizontal-scroll stats cards row (StatsCard ×3)
  - "Upcoming Trips" section heading
  - List of UpcomingTripCard components from API
  - Orange FAB (+) button fixed bottom-right → navigates to `/rides/new`

---

## Phase 4 — Passenger Dashboard

Reference: `screen (2).png`

- [ ] T009 Create `apps/main/src/components/passenger/AvailableRideCard.tsx`:
  - Route: "Origin → Destination" bold
  - Date/time: "Today, 6:00 PM"
  - Price: "65 EGP" bold right-aligned
  - Driver avatar + name + orange star rating
  - Navy "Join Ride" button (right side)
  - White card with subtle shadow, rounded-xl

- [ ] T010 Create `apps/main/src/components/passenger/JoinedRideCard.tsx` (for horizontal scroll):
  - Status badge top-left: UPCOMING (green border) or COMPLETED, etc.
  - Date/time right of badge
  - Price top-right
  - Route with dot-line connector: origin dot → destination dot
  - Card is fixed-width for horizontal scroll container

- [ ] T011 Rebuild `apps/main/src/app/(passenger)/dashboard/page.tsx`:
  - TopBar (passenger variant)
  - "GOOD MORNING" orange small-caps label + "Welcome back, [name]" large bold navy
  - "Available Rides Near You" heading + filter icon → list of AvailableRideCard
  - "My Joined Rides" heading + "View all" orange link + horizontal-scroll JoinedRideCard row
  - Empty state if no rides available

---

## Phase 5 — Validation

- [ ] T012 Run token grep to confirm zero hardcoded color utilities remain after the redesign
- [ ] T013 Run `pnpm --filter main typecheck` — zero errors
- [ ] T014 Visual review: open each dashboard at 375px width and compare side-by-side with reference screenshots
- [ ] T015 Verify role-based routing still works: driver account lands on driver dashboard, passenger account lands on passenger dashboard

---

## Notes for when we resume

- The image files at `C:\Users\ADAM\AppData\Local\Temp\screen (2).png` and `screen (3).png` may be gone by then — re-share them at the start of the implementation session
- There is a third stats card partially visible in the driver design (cut off on the right) — likely a Rating card; confirm with user when resuming
- The passenger "Find a Ride" tab likely leads to a search/filter screen not shown in this design — needs a new design or defer
- Check if `/dashboard` routes exist or if we need to create them (currently the driver lands on `/rides`)
