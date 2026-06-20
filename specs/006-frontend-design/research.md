# Research: Frontend Design System & Screen Library

**Feature**: `006-frontend-design` | **Date**: 2026-06-20

---

## R-001: Design Token Implementation Strategy

**Decision**: CSS custom properties in `globals.css` + Tailwind `theme.extend` references

**Rationale**: This is the standard shadcn/ui convention already partially in use (`packages/ui`). CSS vars at `:root` mean token values can be overridden at runtime (useful for theming later) without rebuilding CSS. Tailwind `theme.extend.colors` maps named tokens to `var(--color-*)` so classes like `text-brand-primary` and `bg-surface-card` work naturally and are tree-shakeable.

**Alternatives Considered**:
- Direct hex values in `theme.extend` — simpler but prevents runtime theming and diverges from shadcn/ui convention already used in the project.
- Separate design token JSON file + style-dictionary — correct at scale (50+ tokens) but overkill for an MVP with ~30 tokens; adds a build step with no payoff for one app.

---

## R-002: Color Palette

**Decision**: Deep navy primary + warm amber accent

| Role | Token Name | Value | Rationale |
|------|-----------|-------|-----------|
| Brand primary | `--color-brand-primary` | `#1B3A6B` | Deep Egyptian blue — conveys trust and reliability; matches Egyptian governmental + transportation branding |
| Brand primary hover | `--color-brand-primary-hover` | `#2D5AA8` | Lighter for hover/focus rings |
| Brand accent | `--color-brand-accent` | `#E8A217` | Warm amber — energy, movement, Cairo sun; used for CTAs and highlights |
| Surface background | `--color-surface-bg` | `#F8F9FA` | Off-white page background |
| Surface card | `--color-surface-card` | `#FFFFFF` | Card / panel background |
| Surface overlay | `--color-surface-overlay` | `rgba(0,0,0,0.5)` | BottomSheet backdrop |
| Text primary | `--color-text-primary` | `#111827` | Main body text |
| Text secondary | `--color-text-secondary` | `#374151` | Supporting text |
| Text muted | `--color-text-muted` | `#6B7280` | Timestamps, captions |
| Text destructive | `--color-text-destructive` | `#DC2626` | Error messages |
| Border default | `--color-border-default` | `#E5E7EB` | Card borders, dividers |
| Border focus | `--color-border-focus` | `#2D5AA8` | Input focus ring |
| Status scheduled | `--color-status-scheduled` | `#2563EB` | Blue — upcoming |
| Status in-progress | `--color-status-in-progress` | `#D97706` | Amber — active |
| Status completed | `--color-status-completed` | `#16A34A` | Green — done |
| Status cancelled | `--color-status-cancelled` | `#DC2626` | Red — ended |
| Status success bg | `--color-status-success-bg` | `#DCFCE7` | Badge/pill background for completed |
| Status warning bg | `--color-status-warning-bg` | `#FEF3C7` | Badge/pill background for in-progress |
| Status info bg | `--color-status-info-bg` | `#DBEAFE` | Badge/pill background for scheduled |
| Status error bg | `--color-status-error-bg` | `#FEE2E2` | Badge/pill background for cancelled |

**Alternatives Considered**:
- Purple/teal palette — too tech-startup generic; doesn't fit Egyptian market aesthetic.
- Orange primary — used by competitors (EasyBus); risks brand confusion.

---

## R-003: Map Library

**Decision**: `react-leaflet` v4 + `leaflet` with OpenStreetMap tiles (already present as `RideMap.tsx` exists)

**Rationale**: OSM + OSRM is the approved tech stack. Leaflet is the standard OSM rendering library for React. `react-leaflet` v4 supports Next.js 14 with dynamic imports (`next/dynamic` + `ssr: false`) to avoid server-side rendering issues. The existing `RideMap.tsx` already uses this approach.

**Full-screen treatment**: The create ride map uses `position: fixed; inset: 0; z-index: 0` for the map container, with the `BottomSheet` rendered above it at `z-index: 10`.

**Tile server**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` (free OSM CDN, already used in development).

**Fallback**: If tiles fail to load, Leaflet renders a blank gray background — the BottomSheet form remains functional. No crash.

**Alternatives Considered**:
- Mapbox GL JS — requires API key + paid tier at scale; proprietary; against the OSM mandate.
- Google Maps — same concerns.

---

## R-004: BottomSheet Implementation Pattern

**Decision**: Pure CSS via `transform: translateY` + `transition` + React `createPortal` to `document.body`

**Rationale**: No new npm package needed. CSS transitions are GPU-accelerated (`transform` triggers compositor layer). Portal to `document.body` prevents clipping by any `overflow: hidden` ancestor on the screen. The `isOpen` prop controls `translateY(0)` (open) vs `translateY(100%)` (closed). A backdrop `div` with `bg-surface-overlay` handles tap-to-dismiss.

**Key implementation details**:
- Use `will-change: transform` on the sheet panel to hint the browser to promote it to its own layer.
- `transition: transform 300ms ease-out` on the panel; `transition: opacity 300ms` on the backdrop.
- Prevent body scroll while open with `document.body.style.overflow = 'hidden'` (restored on close).
- `maxHeightPercent` prop defaults to 65 (65% of `window.innerHeight`); set via inline style.

**Alternatives Considered**:
- Framer Motion `AnimatePresence` — smooth but adds ~30KB to bundle; overkill for one component.
- Radix UI Dialog — designed for modals, not slide-up panels; the transform direction and drag handle are non-standard.
- `@radix-ui/react-dialog` with custom positioning — possible but fighting the library.

---

## R-005: OTP Segmented Input Auto-Advance

**Decision**: Ref array + `onChange` advance + `onKeyDown` backspace retreat + `onPaste` distribute

**Rationale**: The most robust pattern for mobile OTP inputs. A `useRef<(HTMLInputElement | null)[]>([])` array holds refs to each box. On `onChange`, if a single digit is entered and the current box is not the last, `refs[i + 1].focus()` is called. On `onKeyDown` for `Backspace` with an empty box, `refs[i - 1].focus()` is called. On `onPaste`, the pasted string is split into characters and distributed across boxes in order; excess characters are discarded.

**Each box renders as**: `<input type="text" inputMode="numeric" maxLength={1} pattern="[0-9]" />` — `maxLength={1}` limits to one character; `inputMode="numeric"` triggers the numeric keyboard on iOS/Android.

**Alternatives Considered**:
- Single `<input type="text" maxLength={6}>` with custom overlay styling — avoids ref complexity but paste-to-fill is trivial and backspace behavior is unreliable. Rejected because FR-006 mandates per-digit boxes.
- `react-otp-input` npm package — works but adds a dependency for ~60 lines of logic we can own.

---

## R-006: Component Export Strategy

**Decision**: Barrel export from `apps/main/src/components/index.ts`

**Rationale**: FR-021 requires all 5 components to be importable without traversing more than one directory level up. A barrel file at `src/components/index.ts` that re-exports all 5 satisfies this. Callers use `import { RideCard, BottomSheet } from '@/components'` or `import { RideCard } from '../../components'`.

**What gets exported**: `BottomSheet`, `RideCard`, `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions`. Other components (auth, verification, etc.) are NOT in this barrel — they are screen-local and not required to be in the shared library.

---

## R-007: Verification Status Screen — Role-Aware CTA

**Decision**: Read user role from auth context and conditionally render CTA destination

**Rationale**: The `(auth)` route group already establishes the user's role after role selection (stored in Supabase `profiles.role`). The `VerificationStatus` component receives the role as a prop (or reads it from a shared hook) and renders the appropriate CTA label and navigation target. No separate screen per role needed.

**CTA mapping**:
- Driver, approved → "Go to my rides" → `/rides` (driver dashboard)
- Passenger, approved → "Find a ride" → `/search` (ride search — defined in Phase 6; component links to it now, page will exist later)
