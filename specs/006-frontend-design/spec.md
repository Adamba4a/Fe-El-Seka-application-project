# Feature Specification: Frontend Design System & Screen Library

**Feature Branch**: `006-frontend-design`

**Created**: 2026-06-20

**Status**: Draft

**Input**: Phase 4.2 — Frontend Design (Stitch MCP): generate polished, mobile-first UI designs for all screens introduced in Phases 3 and 4, and establish the design system all future phases will follow.

## Clarifications

### Session 2026-06-20

- Q: Should the "slide-up form panel" on Create Ride and the "bottom sheet" on Cancel Ride share a single reusable `BottomSheet` base component, or be implemented independently? → A: Extract a shared `BottomSheet` component; add it to the component library alongside the four ride-specific components.
- Q: What does the ride dashboard show when a driver has no rides yet? → A: An illustration with a "Post your first ride" primary button that navigates to the Create Ride screen.
- Q: Should the OTP segmented input auto-advance focus to the next box on digit entry, or require manual navigation? → A: Auto-advance focus to the next box on single-digit entry; support paste-to-fill so the full OTP from an SMS fills all boxes at once.
- Q: What does the "approved" verification status screen's CTA do, and does it differ by role? → A: Role-aware CTA — approved drivers navigate to the ride dashboard; approved passengers navigate to the ride search screen.
- Q: Are loading and error states for async operations formally required, or left implied by the "working interactive states" assumption? → A: Formally required — all async actions must show a loading spinner on the action button (disabled while pending) and display errors inline (below the triggering field or as a banner at the top of the form).

---

## Business Objective *(mandatory)*

Establish a consistent, polished, mobile-first visual identity for the Fe El Seka main app by designing all screens introduced in Phases 3 and 4 under a unified design system. Doing this now — before Phase 5 adds new screens — ensures every subsequent phase inherits established patterns rather than inventing them ad-hoc, eliminating the visual inconsistency that accumulates when design is deferred.

**Constitutional Domain**: Frontend / UI Design

**Affected Applications**: Main App (`apps/main`) — driver and passenger roles

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Design System Foundation (Priority: P1)

A developer opening the main app codebase for the first time finds a single, authoritative token configuration that defines every color, typography size, and spacing value used across the app. No value is hardcoded in any component file — every value references a named token.

**Why this priority**: Without a locked token set, each subsequent phase invents its own values. This story must be complete before any screen work begins so every screen is built on the same foundation.

**Independent Test**: Open the Tailwind configuration in the main app and verify named tokens exist for brand colors, semantic surface colors, text colors, and status colors. Grep all screen and component files for hardcoded hex values or raw pixel sizes — none should appear.

**Acceptance Scenarios**:

1. **Given** the main app Tailwind configuration, **When** a developer inspects it, **Then** it defines at minimum: a primary brand color, a secondary accent color, semantic surface colors (background, card, overlay), semantic text colors (primary, secondary, muted, destructive), and semantic status colors (success, warning, error).
2. **Given** any screen or component file in the main app, **When** it is reviewed for hardcoded values, **Then** no raw hex codes, RGB values, or arbitrary pixel sizes appear — all values reference named design tokens.
3. **Given** the typography scale, **When** applied across screens, **Then** headings (H1–H3), body text, captions, and labels each map to a distinct named token and render consistently across all screens.
4. **Given** the spacing scale, **When** applied across screens, **Then** margins, paddings, and gaps use a consistent set of named steps — no one-off values.

---

### User Story 2 — Auth & Verification Screens (Priority: P2)

A first-time user opens the app and walks through the complete onboarding flow — phone number entry, OTP verification, profile setup, role selection, and identity verification — without encountering any unstyled, placeholder, or visually inconsistent screens.

**Why this priority**: Auth screens are the first thing every user sees. Unpolished onboarding destroys trust before the user ever sees a ride.

**Independent Test**: Run the main app, navigate as an unauthenticated user, and walk through the full onboarding flow end-to-end. Every screen must render with production-quality styling — no "TODO" labels, no unstyled inputs, no placeholder lorem text — and all interactive elements must respond visually to hover and focus states.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user, **When** they open the app, **Then** the phone number entry screen renders with the app's brand colors, a properly styled input field with country code selector, and a clearly labeled primary action button.
2. **Given** the OTP verification screen, **When** displayed, **Then** it shows a segmented input with one box per digit (not a single text field), a countdown timer for the resend window, and a visible resend action that becomes active only after the timer expires. **When** the user enters a digit in any box, focus automatically advances to the next box. **When** the user pastes a full OTP string, all boxes are filled simultaneously.
3. **Given** the profile setup screen, **When** a user uploads a photo, **Then** the upload control shows a circular preview of the selected image before submission.
4. **Given** the role selection screen, **When** displayed, **Then** driver and passenger roles are presented as distinct tappable cards with an icon and a brief description — not as plain radio buttons or a dropdown.
5. **Given** the National ID upload screen (passenger or driver), **When** a user selects an image file, **Then** the screen shows a thumbnail preview of the selected file and a confirmation button that is disabled until a file is selected.
6. **Given** the verification status screen, **When** a user's status is pending, approved, or rejected, **Then** each state has a distinct visual treatment: a neutral waiting illustration for pending, a success illustration with a green confirmation for approved, and a clear error prompt with a "Resubmit" action for rejected. **When** the status is approved and the user is a driver, **Then** the screen shows a "Go to my rides" CTA that navigates to the ride dashboard. **When** the status is approved and the user is a passenger, **Then** the screen shows a "Find a ride" CTA that navigates to the ride search screen.
7. **Given** all auth and verification screens, **When** rendered on a 375px-wide viewport, **Then** no content overflows horizontally and all interactive elements are at least 44×44 px in tap target size.

---

### User Story 3 — Ride Management Screens (Priority: P3)

A verified driver opens their "My Rides" dashboard, creates a ride, views its details, edits a field, and cancels it — navigating through screens that feel like parts of the same coherent product.

**Why this priority**: Ride management is the core driver workflow used on every trip. Visual inconsistency here is felt daily.

**Independent Test**: Log in as a verified driver, open the ride dashboard, create a ride, open its detail screen, edit a field, and cancel it with a reason. Each screen must use the shared token set and component library, with no visual regression between screens.

**Acceptance Scenarios**:

1. **Given** the driver ride dashboard, **When** it renders, **Then** each ride is displayed as a `RideCard` component showing origin, destination, departure time, seat count, price, and a `RideStatusBadge` — all within a single card that fits on a 375px screen without horizontal scrolling.
2. **Given** the "Create Ride" screen, **When** it opens, **Then** a full-screen map occupies the background and a `BottomSheet` appears from the bottom of the screen containing the trip-detail form.
3. **Given** the `BottomSheet` on the Create Ride screen, **When** a driver pins origin and destination on the map, **Then** the panel displays the reverse-geocoded address labels for both points before the form is submitted.
4. **Given** the `BottomSheet` on the Create Ride screen, **When** open, **Then** it occupies no more than 65% of the viewport height, and its drag handle allows the driver to collapse it to reveal the full map.
5. **Given** the ride detail screen, **When** opened, **Then** it shows the `RideStatusBadge` with the current status, the `RideHistoryLog` of all state changes, and the `StartCompleteActions` buttons appropriate to the current status.
6. **Given** the edit ride screen, **When** the driver modifies a field, **Then** unsaved changes are visually indicated (e.g., a dirty-field underline or an "Unsaved changes" banner) before the driver confirms.
7. **Given** the cancel ride flow, **When** the driver taps "Cancel Ride," **Then** a `BottomSheet` slides up over the current screen requiring a cancellation reason input before the confirm button becomes active — no navigation to a separate screen occurs.
8. **Given** a driver who has just been verified and has no rides yet, **When** they open the ride dashboard, **Then** an illustration and a "Post your first ride" button are shown; tapping the button navigates to the Create Ride screen.
9. **Given** all ride management screens, **When** rendered on a 375px-wide viewport, **Then** no content overflows horizontally and all interactive elements are at least 44×44 px in tap target size.

---

### User Story 4 — Core Component Library (Priority: P4)

A developer implementing Phase 5 opens the shared component library and finds `BottomSheet`, `RideCard`, `RideStatusBadge`, `RideHistoryLog`, and `StartCompleteActions` already built, typed, and ready to import — no restyling or prop guessing required.

**Why this priority**: If these components aren't established as reusable units now, every phase that displays ride data will create its own one-off version, leading to drift and duplicate code.

**Independent Test**: Import each of the five components into a blank test page, pass minimum required props, and verify each renders correctly with no additional styling. Run `pnpm --filter main build` — zero TypeScript errors.

**Acceptance Scenarios**:

1. **Given** the `BottomSheet` component, **When** provided with content and an open state of `true`, **Then** it animates into view from the bottom and occupies no more than 65% of viewport height; **When** the open state becomes `false` or the user taps the drag handle, **Then** it animates out and its content is hidden.
2. **Given** the `RideCard` component, **When** provided with origin, destination, departure time, available seats, total seats, price, and status, **Then** it renders a complete, styled ride summary that matches the ride dashboard design.
3. **Given** the `RideStatusBadge` component, **When** passed any valid status (`scheduled`, `in_progress`, `completed`, `cancelled`), **Then** it renders a pill-shaped badge with a human-readable label and the correct semantic status color for that status.
4. **Given** the `RideHistoryLog` component, **When** given a list of history entries, **Then** it renders them in reverse-chronological order as a vertical timeline; each entry shows the action type, actor (driver name or "System"), and timestamp.
5. **Given** the `StartCompleteActions` component, **When** the ride status is `scheduled`, **Then** it shows "Start Ride" and hides "Complete Ride." **When** `in_progress`, it shows "Complete Ride" and hides "Start Ride." **When** `completed` or `cancelled`, it renders nothing.
6. **Given** all five components, **When** the main app build runs, **Then** it completes with zero TypeScript errors and zero type warnings related to these components.

---

### Edge Cases

- What if Stitch MCP generates markup that does not use the established design tokens? Generated output is a scaffold only — it must be reviewed and aligned to the token set before being committed; no generated hex values or inline styles may remain.
- What if a screen requires a component pattern not yet in the library? The new component is added to the library and documented before the screen is finalized; no one-off inline markup substitutes for a missing component.
- What if two screens independently arrive at different card designs for the same data? One canonical component is chosen and both screens updated; duplicate card patterns are not permitted.
- What if the `BottomSheet` on a small screen covers the map entirely on the Create Ride screen? The `BottomSheet` must respect the 65% maximum height constraint and provide a visible drag handle to collapse it.
- What if a screen passes visual review but has TypeScript errors in its prop types? The screen is not considered complete until the main app build passes with zero TypeScript errors.
- What if the map tile server is unreachable in the local Docker environment? The map must degrade gracefully — showing a placeholder background — without crashing the create ride screen.
- What if an async operation (OTP, file upload, ride creation) returns an error? The action button must re-enable, the spinner must disappear, and the error message must appear inline so the user can correct their input and retry without reloading the page.

---

## Requirements *(mandatory)*

### Functional Requirements

**Design System Tokens**

- **FR-001**: The main app MUST have a single, authoritative token configuration. All colors, typography sizes, font weights, and spacing values used in the app MUST be defined as named tokens in this configuration and referenced by name in all screen and component files.
- **FR-002**: The color token set MUST include: at minimum one primary brand color, one secondary/accent color, semantic surface colors (background, card, overlay), semantic text colors (primary, secondary, muted, destructive), and semantic status colors (success, warning, error).
- **FR-003**: The typography scale MUST define distinct named styles for H1, H2, H3, body, caption, and label text.
- **FR-004**: No hardcoded color, font size, or spacing value is permitted in any screen or component file; all values MUST reference named design tokens.

**Auth & Verification Screens**

- **FR-005**: The following screens MUST be fully implemented in the main app with production-quality styling: phone number entry, OTP verification, profile setup (name + avatar), role selection (driver vs. passenger), passenger National ID upload, driver National ID upload, driver license upload, vehicle registration, and verification status (with distinct visual states for pending, approved, and rejected). The approved state MUST display a role-aware CTA: drivers see "Go to my rides" (navigates to ride dashboard); passengers see "Find a ride" (navigates to ride search screen).
- **FR-006**: The OTP input MUST be a segmented control — one input box per digit — not a single text field. Focus MUST automatically advance to the next box when a digit is entered. Pasting a full OTP string MUST distribute digits across all boxes simultaneously (paste-to-fill).
- **FR-007**: The role selection screen MUST present each role as a distinct tappable card with an icon and a brief description.
- **FR-008**: All file-upload screens MUST display a thumbnail preview of the selected file before the user confirms the upload action.
- **FR-009**: All screens MUST be mobile-first and render without horizontal overflow on viewports as narrow as 375px.
- **FR-010**: All interactive elements across all screens MUST have a minimum tap target size of 44×44 px.

**Ride Management Screens**

- **FR-011**: The following screens MUST be fully implemented with production-quality styling: driver ride dashboard ("My Rides"), create ride, ride detail, edit ride, and cancel ride (as a bottom sheet, not a standalone screen).
- **FR-012**: The create ride screen MUST use a full-screen map background with a `BottomSheet` component anchored to the bottom of the viewport for entering trip details. The `BottomSheet` MUST occupy no more than 65% of viewport height and MUST be collapsible via its drag handle to reveal the full map.
- **FR-013**: The ride dashboard MUST use the `RideCard` component for every ride listing; no one-off inline card markup is permitted on this screen. When the driver has no rides, the dashboard MUST display an empty-state illustration and a "Post your first ride" button that navigates to the Create Ride screen.
- **FR-014**: The ride detail screen MUST use `RideStatusBadge`, `RideHistoryLog`, and `StartCompleteActions` as imported components — not inline markup.
- **FR-015**: The cancel ride flow MUST be implemented using the shared `BottomSheet` component appearing over the ride detail screen. The confirm button MUST remain disabled until the driver enters a cancellation reason.

**Core Components**

- **FR-016**: The `RideCard` component MUST accept and display: origin label, destination label, departure date and time, available seats, total seats, price per seat, and ride status (via `RideStatusBadge`).
- **FR-017**: The `RideStatusBadge` component MUST accept a `status` prop (`scheduled` | `in_progress` | `completed` | `cancelled`) and render a pill badge with a human-readable label and a distinct color per status drawn from the semantic status token set.
- **FR-018**: The `RideHistoryLog` component MUST accept a list of history entries and render them in reverse-chronological order as a vertical timeline. Each entry MUST show: action type, actor (driver name or "System"), and timestamp.
- **FR-019**: The `StartCompleteActions` component MUST conditionally render based on ride status: "Start Ride" for `scheduled`, "Complete Ride" for `in_progress`, nothing for `completed` or `cancelled`.
- **FR-020**: The `BottomSheet` component MUST accept: a content slot, an `isOpen` boolean prop, an `onClose` callback, and an optional `maxHeightPercent` prop (defaulting to 65). It MUST render a drag handle, animate open/close via CSS transitions in under 300ms, and be dismissible by tapping the drag handle or the backdrop overlay.
- **FR-021**: All five components (`BottomSheet`, `RideCard`, `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions`) MUST be exported from a shared path within the main app, importable by any screen without traversing more than one directory level up.
- **FR-022**: Every screen that triggers an async operation (OTP submission, file upload, ride creation, ride edit, ride cancellation, profile save) MUST display a loading spinner on the primary action button and disable that button for the duration of the pending request. Errors returned from the operation MUST be displayed inline — either directly below the field that caused the error or as a banner at the top of the form — not as a navigation to a separate error screen.
- **FR-023**: All screens and components introduced in this phase MUST pass `pnpm --filter main build` with zero TypeScript errors.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 13 screens (9 auth/verification + 5 ride management — including the cancel bottom sheet) render without horizontal overflow on a 375px viewport.
- **SC-002**: Zero hardcoded color, font size, or spacing values appear in any screen or component file — 100% of values reference named design tokens, verifiable by grepping for raw hex codes and inline style attributes.
- **SC-003**: All five core components (`BottomSheet`, `RideCard`, `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions`) render correctly when provided with minimum required props, with no additional styling needed by the caller.
- **SC-004**: `pnpm --filter main build` completes with zero TypeScript errors after all screens and components are added.
- **SC-005**: 100% of interactive elements across all screens meet the 44×44 px tap target minimum, verifiable by visual inspection on a 375px viewport.
- **SC-006**: A developer unfamiliar with the project can identify the correct design token for any color or typography need by consulting the token configuration file alone — without reading any screen or component file.
- **SC-007**: `RideCard` and `RideStatusBadge` are reusable in Phase 5–9 screens without modification to the components themselves.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: All screens MUST be mobile-first; desktop viewports must not be actively broken (no horizontal overflow) but are not required to have optimized wide-viewport layouts for MVP.
- **NFR-002**: The full-screen map on the create ride screen MUST display tiles within 3 seconds on a simulated mobile connection (4G throttling in browser DevTools).
- **NFR-003**: The `BottomSheet` open/close animation MUST complete in under 300ms and MUST be implemented using CSS transitions, not JavaScript frame-by-frame animation.
- **NFR-004**: All screen transitions and interactive feedback animations (button press states, form validation indicators) MUST complete in under 300ms.
- **NFR-005**: No screen MUST produce a Cumulative Layout Shift (CLS) score above 0.1 on a 375px mobile viewport after initial paint.
- **NFR-006**: The design token configuration MUST be the single source of truth — the same tokens are consumed by screen files and any preview or documentation tooling without duplication.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `001-platform-foundation` — Monorepo structure (`apps/main`), Next.js 14, Tailwind CSS, and shadcn/ui must be set up and operational.
  - `003-auth-verification` — Defines the auth and verification screens to be designed in this phase; data flow and route structure are consumed as-is.
  - `004-ride-management` — Defines the ride management screens and the `Ride` + `RideHistoryLog` data models that `RideCard`, `RideHistoryLog`, and `StartCompleteActions` are built against.
  - `005-dockerization` — Containerized local environment must be operational so all developers preview screens in an identical environment.

- **External**:
  - Google Stitch MCP — used to generate initial screen scaffold markup; requires an active MCP connection in the Claude Code environment. If unavailable, shadcn/ui primitives are used directly.
  - OpenStreetMap tile server — required to render the map background on the create ride screen.

- **Data**:
  - No new database schema or API changes are introduced by this phase. All screens consume data models and APIs already defined in Phases 3 and 4.

---

## Out-of-Scope

- Arabic/RTL layout — deferred to Phase 14 (Localization); all screens are English-only for MVP.
- Passenger-facing screens (ride search, ride detail for passengers, booking, booking management) — covered by Phase 6.
- Admin app screens — covered by Phase 11.
- Dark mode — not required for MVP.
- Storybook or a component documentation site — components must be self-documenting via TypeScript prop types; a visual catalogue is a post-competition enhancement.
- Skeleton loaders, advanced micro-interactions, and page transition animations beyond the `BottomSheet` — out of scope for MVP.
- Desktop-optimized layouts — screens must not break on wide viewports but are not required to reflow into multi-column or sidebar layouts.
- WCAG accessibility compliance beyond minimum tap target sizes — full accessibility audit is deferred post-competition.
- Automated visual regression testing (e.g., Chromatic, Percy) — deferred; the build-pass requirement (FR-021) is the quality gate for MVP.

---

## Technical Considerations

- All screens are in `apps/main`; driver screens are gated behind the driver role check established in Phase 3, not by a separate app or route prefix.
- The map on the create ride screen uses the OpenStreetMap integration in the approved tech stack; no proprietary map SDK is to be introduced.
- Design tokens are configured in Tailwind's `theme.extend` block so unused utilities are tree-shaken and do not inflate the CSS bundle.
- `shadcn/ui` components are the baseline primitive library; `BottomSheet`, `RideCard`, `RideHistoryLog`, and `StartCompleteActions` are built on top of shadcn primitives — not from scratch.
- Stitch MCP output is a design scaffold, not final code. Every generated file must be reviewed for token alignment, TypeScript correctness, and component reuse before being committed to the branch.
- The `BottomSheet` component uses CSS `transform` and `transition` for animation to avoid layout thrashing on low-end devices; it is shared between the Create Ride form panel and the Cancel Ride flow.
- All component prop interfaces MUST be defined with explicit TypeScript types — no `any`, `object`, or untyped props — so the build enforces correctness at compile time.
- Per the project constitution, business logic (verification gate checks, seat availability) remains in the FastAPI backend; the frontend only presents data and routes the user — no business rules are enforced exclusively client-side.

---

## Assumptions

- Stitch MCP is available and authenticated in the developer's Claude Code session. If it is not available, implementation falls back to shadcn/ui primitives with the established token set — the deliverables and acceptance criteria remain unchanged.
- The OpenStreetMap tile server is reachable from within the Docker network in local development.
- shadcn/ui is already installed and configured in `apps/main` as part of Phase 1; this phase does not reinstall or reconfigure it.
- Screens are generated and reviewed one at a time through iterative Stitch MCP sessions, then committed — not generated all at once in a single batch.
- "Polished" for competition MVP means: correct token usage, no placeholder text, hover and focus states on all interactive elements, loading and error states on all async operations (per FR-022), and mobile-correct tap targets. It does not mean pixel-perfect fidelity to a Figma file that does not exist.
- The driver and passenger roles share the same `apps/main` codebase; role-based screen visibility is handled by the auth system from Phase 3, not by duplicating screen files.
