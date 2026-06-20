# Contract: Component Interfaces

**Feature**: `006-frontend-design` | **Date**: 2026-06-20

All five components listed below MUST be exported from `apps/main/src/components/index.ts`. All prop interfaces use explicit TypeScript types — no `any` or `object`.

---

## 1. BottomSheet

**File**: `apps/main/src/components/ui/BottomSheet.tsx`

```ts
interface BottomSheetProps {
  /** Controls open/closed state */
  isOpen: boolean;
  /** Called when user taps the backdrop or drag handle to close */
  onClose: () => void;
  /** Maximum height as a percentage of viewport height. Default: 65 */
  maxHeightPercent?: number;
  /** Panel content */
  children: React.ReactNode;
}
```

**Behaviour contract**:
- When `isOpen` is `true`: panel is visible (`transform: translateY(0)`), backdrop is shown, body scroll is locked.
- When `isOpen` is `false`: panel slides down (`transform: translateY(100%)`), backdrop fades out, body scroll is restored.
- Transition: `transform 300ms ease-out` on the panel; `opacity 300ms` on the backdrop.
- Rendered via `createPortal(…, document.body)` to escape any ancestor `overflow: hidden`.
- Drag handle: a centered `<div>` (32×4px, rounded, `bg-border-default`) at the top of the panel. Tapping it calls `onClose`.
- Backdrop: full-screen `<div>` with `bg-surface-overlay`, tap calls `onClose`.

---

## 2. RideCard

**File**: `apps/main/src/components/rides/RideCard.tsx`

```ts
import type { Ride } from '@fe-el-seka/shared';

interface RideCardProps {
  ride: Ride;
}
```

**Behaviour contract**:
- Renders a tappable card linking to `/rides/${ride.id}`.
- Displays: origin address, destination address (with directional arrow separator), departure date/time (formatted for `en-EG` locale), available/total seats, price per seat (EGP), and `RideStatusBadge` for `ride.status`.
- All colors use design tokens — no raw Tailwind color utilities.
- Fits within a 375px viewport without horizontal overflow.

---

## 3. RideStatusBadge

**File**: `apps/main/src/components/rides/RideStatusBadge.tsx`

```ts
import type { RideStatus } from '@fe-el-seka/shared';

interface RideStatusBadgeProps {
  status: RideStatus; // 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
}
```

**Behaviour contract**:
- Renders an inline pill (`rounded-full`, `px-2.5`, `py-0.5`, `text-caption`, `font-medium`).
- Color mapping (all via design tokens):

| Status | Text class | Background class |
|---|---|---|
| `scheduled` | `text-status-scheduled` | `bg-status-scheduled-bg` |
| `in_progress` | `text-status-in-progress` | `bg-status-in-progress-bg` |
| `completed` | `text-status-completed` | `bg-status-completed-bg` |
| `cancelled` | `text-status-cancelled` | `bg-status-cancelled-bg` |

- Label mapping: `scheduled` → "Scheduled", `in_progress` → "In Progress", `completed` → "Completed", `cancelled` → "Cancelled".

---

## 4. RideHistoryLog

**File**: `apps/main/src/components/rides/RideHistoryLog.tsx`

```ts
type HistoryAction = 'created' | 'edited' | 'cancelled' | 'started' | 'completed';

interface RideHistoryEntry {
  id: string;
  action: HistoryAction;
  actor_name: string | null;  // null when system-triggered; display as "System"
  timestamp: string;          // ISO 8601
  changed_fields?: string[];  // present on 'edited' entries
}

interface RideHistoryLogProps {
  entries: RideHistoryEntry[];
}
```

**Behaviour contract**:
- Renders entries in reverse-chronological order (newest first).
- Each entry is a row in a vertical timeline: a colored dot on the left, action label + actor name + relative timestamp on the right.
- `actor_name === null` renders as "System".
- `changed_fields` (when present) renders as a comma-separated list below the action label (e.g., "Changed: departure time, price").
- Timestamps formatted as relative time (e.g., "2 hours ago") with full date on hover/long-press.

---

## 5. StartCompleteActions

**File**: `apps/main/src/components/rides/StartCompleteActions.tsx`

```ts
import type { RideStatus } from '@fe-el-seka/shared';

interface StartCompleteActionsProps {
  rideId: string;
  status: RideStatus;
  onStart: () => Promise<void>;
  onComplete: () => Promise<void>;
}
```

**Behaviour contract**:
- `scheduled` → renders "Start Ride" button only. Tapping calls `onStart`; button shows spinner + disabled while pending.
- `in_progress` → renders "Complete Ride" button only. Tapping calls `onComplete`; button shows spinner + disabled while pending.
- `completed` or `cancelled` → renders nothing (`null`).
- On async error from `onStart` / `onComplete`: button re-enables, spinner disappears, caller is responsible for error display (inline error banner on the parent screen).

---

## Barrel Export

**File**: `apps/main/src/components/index.ts`

```ts
export { BottomSheet } from './ui/BottomSheet';
export { RideCard } from './rides/RideCard';
export { RideStatusBadge } from './rides/RideStatusBadge';
export { RideHistoryLog } from './rides/RideHistoryLog';
export { StartCompleteActions } from './rides/StartCompleteActions';
```

Callers: `import { RideCard, RideStatusBadge } from '@/components'`
