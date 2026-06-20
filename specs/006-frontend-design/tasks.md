# Tasks: Frontend Design System & Screen Library

**Input**: Design documents from `specs/006-frontend-design/`

**Prerequisites**: plan.md âœ… spec.md âœ… research.md âœ… data-model.md âœ… contracts/ âœ… quickstart.md âœ…

**Tests**: Not requested â€” no test tasks generated. Build-pass (`pnpm --filter main build`) and the manual walkthrough in `quickstart.md` are the quality gates.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. US1 (tokens) blocks everything. US4 (components) blocks US3 (ride screens). US2 (auth screens) runs parallel to US4.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Which user story this task belongs to (US1â€“US4)

---

## Phase 1: Setup

**Purpose**: Confirm shared-type dependencies resolve before any design work begins.

- [x] T001 Confirm `packages/shared` exports `Ride`, `RideStatus`, and `RideHistoryEntry` types by running `pnpm --filter @fe-el-seka/shared typecheck` â€” exits 0 (note: package is source-first, no build script; typecheck is the correct gate)

---

## Phase 2: User Story 1 â€” Design System Foundation (Priority: P1) ðŸŽ¯ BLOCKS ALL

**Goal**: A single authoritative token configuration exists; every token-named Tailwind utility is available app-wide; zero hardcoded color, font size, or spacing values in any file going forward.

**Independent Test**: Run `pnpm --filter main typecheck` â€” exits 0 with zero TypeScript errors. (Token grep belongs to Phase 6 after all hardcoded colors are removed from components and screens. Full `next build` requires Supabase env vars not available in local dev and has a pre-existing Windows EPERM on standalone symlinks â€” typecheck is the correct gate here.)

- [x] T002 [US1] Add all 20 CSS custom property color tokens from `contracts/design-tokens.md` to `apps/main/src/app/globals.css` under `:root { â€¦ }` â€” do not alter any existing selectors
- [x] T003 [US1] Update `apps/main/tailwind.config.ts` â€” add `theme.extend.colors` mapping for all `brand`, `surface`, `content`, `border`, and `status` token groups per `contracts/design-tokens.md`; `content` maps CSS text-color vars (`--color-text-*`)
- [x] T004 [US1] Update `apps/main/tailwind.config.ts` â€” add `theme.extend.fontSize` with `h1`, `h2`, `h3`, `body`, `body-sm`, `caption`, and `label` entries per `data-model.md` typography table
- [x] T005 [US1] Run `pnpm --filter main build` to confirm token configuration compiles with zero TypeScript errors before any screen work begins (note: Windows EPERM on standalone symlinks is pre-existing and unrelated to tokens; `pnpm --filter main typecheck` exits 0)

**Checkpoint**: Token classes (e.g., `text-content-primary`, `bg-surface-card`, `text-status-scheduled`) are now available in `apps/main`. All subsequent tasks MUST use these token classes exclusively â€” no raw Tailwind color utilities.

---

## Phase 3: User Story 4 â€” Core Component Library (Priority: P4) ðŸ”’ BLOCKS US3

**Goal**: Five typed, token-based components exported from a single barrel path; the shared `BottomSheet` component is functional and animated; all four existing ride components are free of hardcoded colors.

**Independent Test**: Import all five from `@/components`, render with minimum props â€” no runtime errors, no TypeScript errors, no raw color utilities. `pnpm --filter main typecheck` exits 0.

- [x] T006 [US4] Build `apps/main/src/components/ui/BottomSheet.tsx` â€” implement per `contracts/component-interfaces.md`: React `createPortal` to `document.body`; `isOpen` controls `transform: translateY(0/100%)`; CSS `transition: transform 300ms ease-out` on the panel; `opacity 300ms` transition on the `bg-surface-overlay` backdrop; drag handle (32Ã—4px centered pill, `bg-border-default`); `maxHeightPercent` prop (default 65, applied as inline `max-height: ${maxHeightPercent}vh`); body scroll lock when open (`document.body.style.overflow`); `onClose` called on backdrop tap or drag handle tap; all colors via token classes
- [x] T007 [P] [US4] Polish `apps/main/src/components/rides/RideCard.tsx` â€” replace `border-gray-200` â†’ `border-border-default`, `bg-white` â†’ `bg-surface-card`, `hover:border-gray-400` â†’ `hover:border-brand-primary`, `text-gray-900` â†’ `text-content-primary`, `text-gray-500` â†’ `text-content-muted`, `text-gray-400` â†’ `text-content-muted`, `text-gray-700 font-medium` â†’ `text-content-secondary font-medium`; verify `RideStatusBadge` is used for status (it is)
- [x] T008 [P] [US4] Polish `apps/main/src/components/rides/RideStatusBadge.tsx` â€” replace hardcoded `bg-blue-100 text-blue-800` / `bg-yellow-100 text-yellow-800` / `bg-green-100 text-green-800` / `bg-red-100 text-red-800` with `bg-status-scheduled-bg text-status-scheduled` / `bg-status-in-progress-bg text-status-in-progress` / `bg-status-completed-bg text-status-completed` / `bg-status-cancelled-bg text-status-cancelled` respectively
- [x] T009 [P] [US4] Read and polish `apps/main/src/components/rides/RideHistoryLog.tsx` â€” apply token classes throughout; ensure entries render in reverse-chronological order (newest first); add `actor_id === null` â†’ display "System"; add comma-separated `changed_fields` list when present; each entry: colored dot (status-appropriate token color) + action label + actor + relative timestamp (from `entry.created_at`)
- [x] T010 [P] [US4] Read and polish `apps/main/src/components/rides/StartCompleteActions.tsx` â€” apply token classes; verify conditional render: `scheduled` â†’ "Start Ride" only, `in_progress` â†’ "Complete Ride" only, `completed`/`cancelled` â†’ `null`; add loading spinner + disabled state on each button while its async handler is pending (FR-022); button re-enables on error
- [x] T011 [US4] Create `apps/main/src/components/index.ts` â€” barrel export: `export { BottomSheet } from './ui/BottomSheet'`, `export { RideCard } from './rides/RideCard'`, `export { RideStatusBadge } from './rides/RideStatusBadge'`, `export { RideHistoryLog } from './rides/RideHistoryLog'`, `export { StartCompleteActions } from './rides/StartCompleteActions'`
- [x] T012 [US4] Run `pnpm --filter main typecheck` â€” zero TypeScript errors on Phase 3 components

**Checkpoint**: All five components importable from `@/components`. `RideStatusBadge` uses only token classes. `BottomSheet` animates correctly in a browser. `StartCompleteActions` shows spinner on async action.

---

## Phase 4: User Story 2 â€” Auth & Verification Screens (Priority: P2)

**Goal**: All 9 auth/verification screens render with production-quality token-based styling, OTP auto-advances and supports paste-to-fill, role selection uses card components, file uploads show thumbnail previews, and the verification status screen has three distinct visual states with a role-aware approved CTA.

**Independent Test**: Navigate all 9 screens at 375px viewport â€” no horizontal overflow, no hardcoded colors, all buttons â‰¥44Ã—44px, OTP auto-advance works, photo/doc thumbnails appear on file select. `pnpm --filter main typecheck` exits 0.

- [x] T013 [P] [US2] Polish `apps/main/src/app/(auth)/login/page.tsx` â€” replace `bg-blue-600` button â†’ `bg-brand-primary hover:bg-brand-primary-hover`, `border` input â†’ `border-border-default focus:border-border-focus`, `text-gray-500` â†’ `text-content-muted`, `text-red-500` error â†’ `text-content-destructive`; add loading spinner on button while `loading=true` (spinner + disabled already exists â€” ensure it uses token classes)
- [x] T014 [P] [US2] Polish `apps/main/src/components/auth/OtpInput.tsx` â€” implement auto-advance: on `onChange` with a single digit entered, call `refs[i+1]?.focus()`; implement backspace retreat: on `onKeyDown` with `Backspace` and empty box, call `refs[i-1]?.focus()`; implement paste-to-fill: on `onPaste`, split pasted string into digits and distribute across all boxes; apply token classes throughout (replace any raw color utilities)
- [x] T015 [US2] Polish `apps/main/src/app/(auth)/otp/page.tsx` â€” wire updated `OtpInput` (T014); verify countdown timer styling uses token classes; resend button disabled until timer reaches 0; error messages use `text-content-destructive`; loading state on submit per FR-022
- [x] T016 [P] [US2] Polish `apps/main/src/components/auth/RoleSelector.tsx` â€” transform to card-based layout: each role (driver/passenger) rendered as a tappable `<button>` card with icon, role name in `text-h3`, brief description in `text-body-sm text-content-muted`, `border-border-default` border, `bg-surface-card` background, `hover:border-brand-primary` on hover, selected state uses `border-brand-primary bg-status-info-bg` (where `status-info-bg` = `status-scheduled-bg`); NOT radio buttons or a dropdown
- [x] T017 [US2] Polish `apps/main/src/app/(auth)/role-select/page.tsx` â€” wire `RoleSelector` card component; apply token classes to page wrapper and heading
- [x] T018 [P] [US2] Polish `apps/main/src/components/profile/ProfilePhotoUpload.tsx` â€” on file select: show circular thumbnail preview (`rounded-full`, `object-cover`, 80Ã—80px) of the selected `File` via `URL.createObjectURL`; revoke object URL on unmount; apply token classes
- [x] T019 [US2] Polish `apps/main/src/app/(onboarding)/profile/page.tsx` â€” wire `ProfilePhotoUpload` circular preview; apply token classes to form inputs and submit button; loading state on submit per FR-022
- [x] T020 [P] [US2] Polish `apps/main/src/components/verification/DocumentUpload.tsx` â€” on file select: show rectangular thumbnail preview of selected image (`object-contain`, max 120px height) via `URL.createObjectURL`; revoke URL on unmount; apply token classes throughout; note: submit button and loading state belong in the parent page, not in this reusable picker component
- [x] T021 [US2] Polish `apps/main/src/app/(onboarding)/verify-id/page.tsx` â€” wire `DocumentUpload` for passenger National ID; apply token classes; heading and helper text in token typography
- [x] T022 [US2] Polish `apps/main/src/app/(onboarding)/driver/verify-documents/page.tsx` â€” wire `DocumentUpload` for driver National ID upload and driver license upload (two separate upload sections or two-step flow as currently structured); apply token classes; loading and error states per FR-022
- [x] T023 [P] [US2] Polish `apps/main/src/components/vehicle/VehicleRegistrationForm.tsx` â€” apply token classes to all inputs, labels, select elements, and submit button; add loading spinner on submit while pending; inline error per FR-022
- [x] T024 [US2] Polish `apps/main/src/app/(onboarding)/driver/register-vehicle/page.tsx` â€” wire `VehicleRegistrationForm`; apply token classes; heading in token typography
- [x] T025 [US2] Polish `apps/main/src/components/verification/VerificationStatus.tsx` â€” implement three distinct visual states: (1) **pending** â€” neutral waiting illustration (SVG or image), "We're reviewing your documents" message in `text-content-secondary`, no CTA; (2) **approved** â€” success illustration, "You're verified!" heading in `text-h2`, role-aware CTA button: driver role â†’ "Go to my rides" â†’ navigates to `/rides`; passenger role â†’ "Find a ride" â†’ navigates to `/search`; button uses `bg-brand-primary` styling; (3) **rejected** â€” error illustration or icon in `text-content-destructive`, rejection reason text, "Resubmit" button â†’ navigates back to the appropriate upload screen; all states use token classes
- [x] T026 [US2] Run `pnpm --filter main typecheck` â€” zero TypeScript errors on Phase 4 screens
- [x] T027 [US2] Visual walkthrough of all 9 auth/verification screens at 375px (quickstart.md step 4) â€” confirm no horizontal overflow, all interactive elements â‰¥44Ã—44px tap target, OTP auto-advance works, paste-to-fill works, thumbnails appear on file select, verified status screen CTA navigates correctly by role

**Checkpoint**: All auth and verification screens are polished and mobile-correct. OTP segmented input auto-advances and supports paste. Document upload shows thumbnails. Verification approved state shows role-aware CTA.

---

## Phase 5: User Story 3 â€” Ride Management Screens (Priority: P3)

**Goal**: All 5 ride management screens render with production-quality token-based styling; the full-screen map + BottomSheet create ride pattern works; the empty dashboard state is present; cancel ride uses BottomSheet; edit screen shows dirty-field indicator. Depends on Phase 3 (BottomSheet + ride components).

**Independent Test**: Log in as a verified driver, walk through dashboard â†’ create â†’ detail â†’ edit â†’ cancel at 375px â€” no horizontal overflow, all interactive elements â‰¥44Ã—44px, BottomSheet opens/closes within 300ms, empty state visible before first ride. `pnpm --filter main typecheck` exits 0.

- [x] T028 [US3] Polish `apps/main/src/components/rides/RideMap.tsx` â€” set map container to `position: fixed; inset: 0; z-index: 0` (full-screen background); OSM tile graceful fallback (gray background placeholder when tiles fail â€” Leaflet default); ensure `dynamic` import with `ssr: false` is in place for Next.js 14; apply token classes to any overlaid UI elements
- [x] T029 [US3] Polish `apps/main/src/app/(driver)/rides/page.tsx` (dashboard) â€” add empty state: when the rides list is empty, render a centered illustration SVG + "No rides yet" heading + "Post your first ride" `<Link>` button (â†’ `/rides/new`) styled as `bg-brand-primary text-content-inverse`; rides list renders each ride as `<RideCard ride={ride} />` imported from `@/components`; add status filter tabs (`All`, `Scheduled`, `In Progress`, `Completed`, `Cancelled`) in token classes above the list; apply token classes throughout
- [x] T030 [US3] Polish `apps/main/src/app/(driver)/rides/new/page.tsx` (create ride) â€” compose `<RideMap />` as full-screen background and `<BottomSheet isOpen={true} onClose={â€¦} maxHeightPercent={65}>` containing `<RideForm />` imported from rides components; BottomSheet should default open on page load and be collapsible to reveal the map; after map pin drop, pass reverse-geocoded address labels as props to `RideForm`; apply token classes to page wrapper; loading + error states on form submit per FR-022
- [x] T031 [US3] Polish `apps/main/src/components/rides/RideForm.tsx` â€” apply token classes to all inputs, labels, and the submit button; submit button shows loading spinner + disabled while pending; inline field-level error messages in `text-content-destructive`; price input labeled "EGP per seat"
- [x] T032 [US3] Polish `apps/main/src/app/(driver)/rides/[id]/page.tsx` (detail) â€” import `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions`, `BottomSheet` from `@/components`; add "Cancel Ride" button (only visible for `scheduled` status) that sets `isCancelOpen=true` on a `BottomSheet`; inside the `BottomSheet`: "Cancel Ride" heading, `<textarea>` for cancellation reason (`border-border-default`), confirm button disabled until reason is non-empty, loading state on confirm submit, close button calls `onClose`; apply token classes throughout the page
- [x] T033 [US3] Polish `apps/main/src/app/(driver)/rides/[id]/edit/page.tsx` (edit) â€” add dirty-field detection: track original field values on mount; show `"Unsaved changes"` banner (`bg-status-in-progress-bg text-status-in-progress border-border-default`) when any field differs from original; apply token classes to all inputs and buttons; loading + error states per FR-022
- [x] T034 [US3] Run `pnpm --filter main typecheck` â€” zero TypeScript errors on Phase 5 screens
- [x] T035 [US3] Visual walkthrough of all 5 ride management screens at 375px (quickstart.md step 5) â€” confirm empty state, BottomSheet create ride, BottomSheet cancel flow, dirty-field indicator, all â‰¥44Ã—44px tap targets, no horizontal overflow

**Checkpoint**: Full driver ride management flow is polished end-to-end. BottomSheet is used for both form entry and cancel flow. Empty state guides new drivers to their first ride.

---

## Phase 6: Polish & Final Validation

**Purpose**: Cross-cutting quality gate â€” ensure the complete app passes all spec acceptance criteria.

- [x] T036 Run token validation grep (quickstart.md step 3) across `apps/main/src/components` and `apps/main/src/app` â€” expected: zero matches; any match is a violation that must be fixed before proceeding
- [x] T037 Run final `pnpm --filter main build` with a valid `.env.local` (containing `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, and `NEXT_PUBLIC_NOMINATIM_URL`) — all four are required: the first three are validated by `src/lib/env.ts` at server startup; `NEXT_PUBLIC_NOMINATIM_URL` powers reverse-geocoding in `RideMap`; `BACKEND_INTERNAL_URL` is optional (falls back to `NEXT_PUBLIC_API_URL`); zero TypeScript errors and successful page generation across the entire `apps/main` package (FR-023 / SC-004); on Windows, EPERM on standalone symlinks is a known platform limitation and does not count as a failure if TypeScript and page generation both pass
- [x] T038 [P] Verify `BottomSheet` animation runs on the compositor thread (quickstart.md step 7) â€” open Chrome DevTools Performance panel, record BottomSheet open and close, confirm `transform` animation frames appear in the Compositor lane (green), total duration â‰¤300ms (NFR-003)
- [x] T039 [P] Run Lighthouse mobile audit on `/login`, `/rides`, and `/rides/new` (quickstart.md step 8) â€” verify CLS â‰¤0.1 on each screen (NFR-005)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  â””â”€â–º Phase 2 (US1 â€” Tokens) â—„â”€â”€ BLOCKS ALL
        â”œâ”€â–º Phase 3 (US4 â€” Components) â—„â”€â”€ BLOCKS Phase 5
        â”‚     â””â”€â–º Phase 5 (US3 â€” Ride Screens)
        â””â”€â–º Phase 4 (US2 â€” Auth Screens) [parallel with Phase 3]
              â””â”€â–º Phase 6 (Validation) [after Phases 3, 4, 5]
```

### User Story Dependencies

- **US1 (P1)**: No dependencies â€” start immediately after T001
- **US4 (P4)**: Depends on US1 (token classes must exist before component polishing)
- **US2 (P2)**: Depends on US1; runs parallel to US4
- **US3 (P3)**: Depends on US1 AND US4 (requires `BottomSheet` and polished ride components)

### Within Each Phase

- Tasks marked `[P]` within the same phase can run simultaneously (they touch different files)
- Page tasks (T015, T017, T019, T021, T022, T024) depend on their respective component tasks (T014, T016, T018, T020, T020, T023) in Phase 4
- Commit after each task or logical group

### Parallel Opportunities

**Phase 3 (US4)** â€” run T007â€“T010 together (four different component files):
```
T007: BottomSheet.tsx (new)
T008: RideCard.tsx     [P]
T009: RideStatusBadge.tsx [P]
T010: RideHistoryLog.tsx  [P]
T011: StartCompleteActions.tsx [P]
```

**Phase 4 (US2)** â€” run component polishes together, then page polishes after:
```
Round 1 (parallel):
  T013: login/page.tsx
  T014: OtpInput.tsx
  T016: RoleSelector.tsx
  T018: ProfilePhotoUpload.tsx
  T020: DocumentUpload.tsx
  T023: VehicleRegistrationForm.tsx

Round 2 (after Round 1):
  T015: otp/page.tsx         (depends on T014)
  T017: role-select/page.tsx (depends on T016)
  T019: profile/page.tsx     (depends on T018)
  T021: verify-id/page.tsx   (depends on T020)
  T022: verify-documents/page.tsx (depends on T020)
  T024: register-vehicle/page.tsx (depends on T023)
  T025: VerificationStatus.tsx (independent)
```

**Phases 3 and 4 run in parallel** (different files, different phases of feature, both depend only on Phase 2):
```
Developer A: Phase 3 (US4 â€” Component Library)
Developer B: Phase 4 (US2 â€” Auth Screens)
```

---

## Implementation Strategy

### MVP First (US1 + US4 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: US1 Token Foundation (T002â€“T005)
3. Complete Phase 3: US4 Component Library (T006â€“T012)
4. **STOP and VALIDATE**: Import all 5 components in a test page, run build gate, run token grep
5. Components are now reusable for all future phases

### Incremental Delivery

1. Phase 1 + 2 â†’ Token foundation live â†’ All subsequent work builds on tokens
2. Phase 3 â†’ Component library done â†’ Phase 5 can begin
3. Phase 4 â†’ Auth screens polished â†’ Onboarding flow looks production-ready
4. Phase 5 â†’ Ride screens polished â†’ Complete driver experience polished
5. Phase 6 â†’ Final validation â†’ Branch ready for PR

### Stitch MCP Integration

For each screen or component being polished, the recommended workflow is:

1. Use Stitch MCP to generate a design for that screen using the token names from `contracts/design-tokens.md`
2. Review generated output: confirm token class usage, TypeScript correctness, no hardcoded values
3. Apply aligned output to the file
4. Run `pnpm --filter main build` after each file to catch TypeScript errors early

---

## Notes

- `[P]` tasks touch different files and have no in-progress dependencies â€” run them together
- `[Story]` label maps each task to a spec user story for traceability
- Each phase ends with a build gate task â€” stop and fix before continuing
- Token grep (T036) is the definitive zero-hardcoded-value check â€” run it last
- The `BottomSheet` (T006) is the most complex new component â€” build and test it in isolation before integrating into ride screens (T030, T032)
- `StartCompleteActions` (T010) requires testing the loading/disabled state manually â€” the async handlers are provided by the parent screen, not the component
- Avoid: editing the same file in parallel tasks, adding business logic to frontend components, using `any` types in prop interfaces



