# Implementation Plan: Frontend Design System & Screen Library

**Branch**: `006-frontend-design` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-frontend-design/spec.md`

## Summary

Establish a unified design token system in `apps/main` and polish all screens and components introduced in Phases 3 and 4 to a production-quality, mobile-first standard. The Tailwind config gains a full semantic token set; one new shared `BottomSheet` component is built; four existing ride components (`RideCard`, `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions`) are refactored from hardcoded Tailwind colors to token-based classes; and all 13 screens are polished with Stitch MCP assistance. Every Phase 5–9 screen inherits consistent patterns without per-screen design decisions.

See `research.md` for token, library, and implementation decisions.

---

## Technical Context

**Language/Version**: TypeScript 5.x / Node 20

**Primary Dependencies**: Next.js 14, Tailwind CSS 3, shadcn/ui, react-leaflet (OSM map rendering)

**Storage**: N/A — no database schema or API changes in this phase

**Testing**: `pnpm --filter main build` (TypeScript compile gate + dead-code elimination); manual browser walkthrough per `quickstart.md`

**Target Platform**: Mobile web, 375px primary viewport; desktop (>768px) must render without horizontal overflow

**Project Type**: Monorepo frontend — `apps/main` (combined driver + passenger Next.js 14 app)

**Performance Goals**: Map tiles ≤3s on simulated 4G; `BottomSheet` open/close ≤300ms; CLS ≤0.1 on 375px viewport

**Constraints**: No new backend dependencies; no new npm packages unless strictly required for map rendering; CSS-only animations (no Framer Motion); shadcn/ui primitives as the component base layer

**Scale/Scope**: 13 screens + 5 components; ~1,000 active users at launch

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I — Driver-First Route Sharing | ✅ Pass | No passenger screens in scope; ride dashboard preserves driver perspective |
| II — Route Intelligence | ✅ Pass | No routing logic introduced; map is presentational only |
| III — Trust Before Transportation | ✅ Pass | Verification status screen three-state design preserves trust gating |
| IV — AI-Augmented Transportation | ✅ Pass | No AI components in scope |
| V — Mobile-First UX | ✅ Pass | 375px primary viewport; ≥44×44px tap targets; BottomSheet is mobile-native |
| VI — Modular Domain | ✅ Pass | Design system is a single bounded concern; no cross-domain logic introduced |
| VII — Shared Foundations | ✅ Pass | Tokens in `apps/main/tailwind.config.ts`; ride components in `apps/main/src/components/rides/`; `BottomSheet` in `apps/main/src/components/ui/` (domain-agnostic) |
| Architecture Standards | ✅ Pass | No business logic in frontend; all components are presentational |

**No violations requiring justification.**

**Post-Phase-1 re-check**: Constitution Check passes. The `BottomSheet` component has no domain dependencies and is correctly placed in `ui/`. Ride-specific components stay in `apps/main` (not `packages/ui`) because they depend on `@fe-el-seka/shared` ride types — this is correct domain separation per Principle VII.

---

## Project Structure

### Documentation (this feature)

```text
specs/006-frontend-design/
├── plan.md                         # This file
├── research.md                     # Phase 0 — token, library, and pattern decisions
├── data-model.md                   # Phase 1 — token taxonomy + component prop interfaces
├── quickstart.md                   # Phase 1 — validation walkthrough
├── contracts/
│   ├── design-tokens.md            # Token names, categories, and values
│   └── component-interfaces.md     # TypeScript prop interfaces for all 5 components
└── tasks.md                        # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
apps/main/
├── tailwind.config.ts                            # MODIFY: add design tokens in theme.extend
├── src/
│   ├── app/
│   │   ├── globals.css                           # MODIFY: add CSS custom properties for tokens
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx                    # POLISH: brand tokens, styling pass
│   │   │   └── otp/page.tsx                      # POLISH: auto-advance + paste-to-fill OTP
│   │   ├── (onboarding)/
│   │   │   ├── profile/page.tsx                  # POLISH: circular photo preview, tokens
│   │   │   ├── verify-id/page.tsx                # POLISH: thumbnail preview, tokens
│   │   │   └── driver/
│   │   │       ├── verify-documents/page.tsx      # POLISH: thumbnail preview, tokens
│   │   │       └── register-vehicle/page.tsx      # POLISH: tokens
│   │   └── (driver)/
│   │       ├── rides/page.tsx                    # POLISH: empty state + RideCard list
│   │       ├── rides/new/page.tsx                # POLISH: full-screen map + BottomSheet form
│   │       ├── rides/[id]/page.tsx               # POLISH: RideStatusBadge + RideHistoryLog + StartCompleteActions + BottomSheet cancel
│   │       └── rides/[id]/edit/page.tsx          # POLISH: dirty-field indicator, tokens
│   └── components/
│       ├── index.ts                              # NEW or MODIFY: re-export all 5 components
│       ├── ui/
│       │   └── BottomSheet.tsx                   # NEW: shared slide-up panel
│       ├── auth/
│       │   ├── OtpInput.tsx                      # POLISH: auto-advance, paste-to-fill, tokens
│       │   ├── PhoneInput.tsx                    # POLISH: tokens
│       │   └── RoleSelector.tsx                  # POLISH: card treatment, tokens
│       ├── verification/
│       │   ├── DocumentUpload.tsx                # POLISH: thumbnail preview, tokens
│       │   ├── VerificationStatus.tsx            # POLISH: 3 states, role-aware CTA
│       │   └── PendingApprovalWait.tsx           # POLISH: tokens
│       ├── profile/
│       │   ├── ProfileForm.tsx                   # POLISH: tokens
│       │   └── ProfilePhotoUpload.tsx            # POLISH: circular preview, tokens
│       ├── vehicle/
│       │   └── VehicleRegistrationForm.tsx       # POLISH: tokens
│       └── rides/
│           ├── RideCard.tsx                      # POLISH: hardcoded colors → token classes
│           ├── RideStatusBadge.tsx               # POLISH: hardcoded colors → semantic status tokens
│           ├── RideHistoryLog.tsx                # POLISH: tokens
│           ├── StartCompleteActions.tsx          # POLISH: tokens
│           ├── RideForm.tsx                      # POLISH: used inside BottomSheet on create/edit
│           └── RideMap.tsx                       # POLISH: full-screen height, BottomSheet overlay

packages/
└── shared/
    └── src/types/rides.ts                        # READ-ONLY: RideStatus type consumed by components
```

**Structure Decision**: Monorepo (Option 4). Ride-domain components remain in `apps/main/src/components/rides/` because they import `RideStatus` and `Ride` from `@fe-el-seka/shared`. The new `BottomSheet` is domain-agnostic and lives in `apps/main/src/components/ui/`. All 5 spec-required components are re-exported from `apps/main/src/components/index.ts` so callers import from one path (`@/components` or `../../components`).
