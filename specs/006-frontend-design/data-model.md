# Data Model: Frontend Design System & Screen Library

**Feature**: `006-frontend-design` | **Date**: 2026-06-20

> This phase introduces no new database entities or API endpoints. The "data model" here is the design token taxonomy and the component prop interfaces that form the component library's public contract.

---

## Design Token Taxonomy

All tokens are defined as CSS custom properties on `:root` in `apps/main/src/app/globals.css` and mapped to named Tailwind utilities in `apps/main/tailwind.config.ts`.

### Color Tokens

| Token Name (CSS var) | Tailwind Class Prefix | Category | Purpose |
|---|---|---|---|
| `--color-brand-primary` | `brand-primary` | Brand | Primary CTA buttons, active nav, key accents |
| `--color-brand-primary-hover` | `brand-primary-hover` | Brand | Hover/focus state of primary elements |
| `--color-brand-accent` | `brand-accent` | Brand | Highlights, secondary CTAs, amber accents |
| `--color-surface-bg` | `surface-bg` | Surface | Page background |
| `--color-surface-card` | `surface-card` | Surface | Card and panel backgrounds |
| `--color-surface-overlay` | `surface-overlay` | Surface | BottomSheet backdrop |
| `--color-surface-destructive` | `surface-destructive` | Surface | Background for destructive action buttons |
| `--color-text-primary` | `text-primary` | Text | Main body and heading text |
| `--color-text-secondary` | `text-secondary` | Text | Supporting text |
| `--color-text-muted` | `text-muted` | Text | Captions, timestamps, placeholder |
| `--color-text-inverse` | `text-inverse` | Text | Text on top of dark/primary-colored backgrounds |
| `--color-text-destructive` | `text-destructive` | Text | Inline error messages |
| `--color-border-default` | `border-default` | Border | Card borders, input borders, dividers |
| `--color-border-focus` | `border-focus` | Border | Input focus rings |
| `--color-status-scheduled` | `status-scheduled` | Status | Text/icon for `scheduled` rides |
| `--color-status-in-progress` | `status-in-progress` | Status | Text/icon for `in_progress` rides |
| `--color-status-completed` | `status-completed` | Status | Text/icon for `completed` rides |
| `--color-status-cancelled` | `status-cancelled` | Status | Text/icon for `cancelled` rides |
| `--color-status-scheduled-bg` | `status-scheduled-bg` | Status | Badge background for `scheduled` |
| `--color-status-in-progress-bg` | `status-in-progress-bg` | Status | Badge background for `in_progress` |
| `--color-status-completed-bg` | `status-completed-bg` | Status | Badge background for `completed` |
| `--color-status-cancelled-bg` | `status-cancelled-bg` | Status | Badge background for `cancelled` |

### Typography Tokens

Defined in Tailwind `theme.extend.fontSize`. All use a 1.5 line-height baseline.

| Token | Tailwind Class | Size | Weight | Use |
|---|---|---|---|---|
| `text-h1` | `text-h1` | 30px / 1.2 | 700 | Page titles |
| `text-h2` | `text-h2` | 24px / 1.3 | 700 | Section headings |
| `text-h3` | `text-h3` | 20px / 1.3 | 600 | Card headings |
| `text-body` | `text-body` | 16px / 1.5 | 400 | Default body text |
| `text-body-sm` | `text-body-sm` | 14px / 1.5 | 400 | Secondary body text |
| `text-caption` | `text-caption` | 12px / 1.4 | 400 | Timestamps, helper text |
| `text-label` | `text-label` | 14px / 1 | 500 | Form labels, button text |

### Spacing Tokens

Tailwind's default spacing scale is used; no custom spacing tokens are introduced. Components use the existing `p-4`, `gap-3`, `space-y-2` conventions.

---

## Component Prop Interfaces

Full TypeScript definitions are in `contracts/component-interfaces.md`. Summarized here for planning reference.

### BottomSheet

```
isOpen: boolean
onClose: () => void
maxHeightPercent?: number  // default: 65
children: React.ReactNode
```

State: open (`isOpen=true`, `translateY(0)`) / closed (`isOpen=false`, `translateY(100%)`)

### RideCard

```
ride: Ride  // from @fe-el-seka/shared
```

Internally uses `RideStatusBadge`. Navigates to `/rides/${ride.id}` on tap.

### RideStatusBadge

```
status: RideStatus  // 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
```

Maps each status to a background token + text token pair.

### RideHistoryLog

```
entries: RideHistoryEntry[]
```

Where `RideHistoryEntry` = `{ id, action, actor_id, created_at, changed_fields? }` (from `@fe-el-seka/shared`).
Rendered in reverse-chronological order (newest first).

### StartCompleteActions

```
rideId: string
status: RideStatus
onStart: () => Promise<void>
onComplete: () => Promise<void>
```

Renders "Start Ride" for `scheduled`, "Complete Ride" for `in_progress`, nothing for `completed` / `cancelled`. Each button shows loading state (spinner + disabled) while its async handler is pending.

---

## Token Invariants

- Every component file MUST use only token-named Tailwind classes for colors (e.g., `text-text-primary`, `bg-surface-card`) — never raw color utilities like `text-gray-900` or `bg-blue-600`.
- The `status-*` token family maps 1:1 to the four `RideStatus` values; no additional status values are introduced in this phase.
- The token taxonomy is the source of truth for color decisions; deviations require updating this file first.
