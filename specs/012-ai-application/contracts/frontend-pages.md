# Frontend Page Contracts: AI Application (Phase 9)

**Feature**: `012-ai-application` | **Date**: 2026-07-01 | **App**: `apps/main`

This document specifies only the **changes** Phase 9 makes to existing pages and the one new component introduced. All unchanged pages are omitted.

---

## New Component: MatchScoreBadge

**File**: `apps/main/src/components/search/MatchScoreBadge.tsx`

**Purpose**: Displays the AI match percentage on ride cards and the ride detail page.

**Props**:
```typescript
interface MatchScoreBadgeProps {
  score_pct: number | null
}
```

**Rendering rules**:
- `null` → renders nothing (no placeholder, no skeleton)
- `0–100` → renders `"{score_pct}% match"` as a pill/badge

**Colour coding**:

| Score | Label colour |
|-------|-------------|
| ≥ 70% | Green (`bg-green-100 text-green-800`) |
| 40–69% | Amber (`bg-amber-100 text-amber-800`) |
| < 40% | Grey (`bg-gray-100 text-gray-600`) |

**Layout**: Inline pill, consistent with existing `RideStatusBadge` sizing and border-radius.

---

## Changed: Search Results Page

**File**: `apps/main/src/app/(passenger)/search/results/page.tsx`

**Change**: Add `MatchScoreBadge` to each ride card.

**Placement**: Below the driver name / departure time row, above the price and seats row.

**Data source**: `candidate.match_score_pct` from `POST /api/v1/search/rides` response.

**Behaviour**:
- When `ai_ranking_active: true` — badge shows for all candidates with their score.
- When `ai_ranking_active: false` (fallback mode) — `match_score_pct` is `null` for all candidates; badges are hidden. No error or notice shown to the passenger.
- Results list is sorted server-side; no client-side re-sort needed.

**No other changes** to the search results page layout.

---

## Changed: Ride Detail Page (Passenger)

**File**: `apps/main/src/app/(passenger)/rides/[id]/page.tsx`

**Change**: Add `MatchScoreBadge` to the ride detail header section.

**Placement**: Alongside the existing driver info / route summary header — same region where the match badge appears on the search card, for visual consistency.

**Data source**: `match_score_pct` from `GET /api/v1/rides/{ride_id}/passenger-detail` response (requires `departure_at` query param, passed from search context or page state).

**Behaviour**:
- When navigating from search results: `departure_at` is available from the search query; badge shows with the same score as the search card.
- When arriving via direct link or deep link: `departure_at` may be absent; `match_score_pct` will be `null`; badge is hidden.
- When AI is unavailable: `match_score_pct` is `null`; badge hidden. No error shown.

---

## Changed: Driver Ride Creation Page

**File**: `apps/main/src/app/(driver)/rides/create/page.tsx`

**Changes**:

1. **Remove** the `price_per_seat` input field from the ride creation form. The form no longer asks the driver for a price.

2. **Add** system fare display on the **success/confirmation screen** (shown after successful `POST /api/v1/rides`):
   - Display: `"Fare: {price_per_seat} EGP per seat"`
   - Style: Read-only information row — not an input, not editable.
   - No explanation of how the fare was computed is shown to the driver.

**Form fields after change**:

| Field | Status |
|-------|--------|
| Vehicle | Unchanged |
| Origin | Unchanged |
| Destination | Unchanged |
| Departure date/time | Unchanged |
| Total seats | Unchanged |
| Notes (optional) | Unchanged |
| ~~Price per seat~~ | **Removed** |

**Confirmation screen additions**:

| Element | Content |
|---------|---------|
| Fare display | `"Fare: {price_per_seat} EGP per seat"` (read-only) |
| All other confirmation fields | Unchanged from Phase 4 |
