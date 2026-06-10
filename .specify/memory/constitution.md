<!--
## Sync Impact Report

**Version Change**: Template (unpopulated) → 1.0.0
**Bump Type**: MINOR — initial constitution creation; all principles and sections are new

### Principles Added (all new)
- I. Driver-First Route Sharing
- II. Route Intelligence Over Geographic Proximity
- III. Trust Before Transportation
- IV. AI-Augmented Transportation
- V. Mobile-First User Experience
- VI. Modular Domain-Driven Architecture
- VII. Shared Foundations, Independent Applications

### Sections Added (all new)
- Technical Standards (Approved Technology Stack, Architecture Standards, Data Standards)
- Security & Privacy Requirements (Identity & Verification, Data Protection, Auditability)
- Real-Time Transportation Requirements
- Development Workflow Standards (Specification-Driven Development, Domain-Based Planning, Quality Standards)
- Governance

### Templates Updated
- `.specify/memory/constitution.md` ✅ Updated (this file)
- `.specify/templates/spec-template.md` ✅ Updated — added Business Objective, Non-Functional Requirements, Dependencies, Out-of-Scope, Technical Considerations (required by constitution §Dev Workflow Standards)
- `.specify/templates/plan-template.md` ✅ Updated — added monorepo project structure option (required by Principle VII)
- `.specify/templates/tasks-template.md` ✅ Aligned — no structural changes required

### Deferred Items
None — all sections fully defined.
-->

# Fe El Seka Constitution

## Core Principles

### I. Driver-First Route Sharing

Fe El Seka is a route-sharing and carpooling platform, not a ride-hailing platform.

Drivers create rides because they are already traveling to a destination. Passengers discover and
join existing rides that align with their journeys.

The platform MUST NOT operate as an on-demand transportation marketplace where passengers request
rides and drivers respond.

All specifications, plans, and implementations MUST preserve this distinction.

---

### II. Route Intelligence Over Geographic Proximity

Matching decisions MUST prioritize route overlap, travel efficiency, and minimal detours rather than
simple straight-line distance calculations.

Transportation decisions MUST be based on actual road networks and routing intelligence.

Route feasibility SHALL be determined through deterministic geospatial calculations; AI MAY enhance
matching quality, ranking, and optimization.

---

### III. Trust Before Transportation

User trust and safety are prerequisites for participation in the platform.

Identity verification, ride transparency, accountability, and traceability are mandatory platform
capabilities.

Passengers and drivers MUST be verifiable entities before participating in ride-sharing activities.

Safety-related decisions MUST take precedence over convenience-related decisions.

---

### IV. AI-Augmented Transportation

Artificial Intelligence is a core capability of Fe El Seka.

AI SHALL enhance:

- Route Matching
- Ride Ranking
- Pricing Recommendations
- Ride Grouping
- Demand Forecasting
- Future Fraud Detection

AI systems MUST remain explainable, auditable, and independently deployable.

Deterministic transportation logic remains the source of truth for route feasibility and eligibility.

The platform architecture MUST support continuous model improvement without requiring major
architectural redesign.

---

### V. Mobile-First User Experience

The primary platform experience is mobile-first.

Ride creation, ride discovery, booking, tracking, and ride management workflows MUST prioritize
speed, simplicity, and clarity.

The platform MUST minimize user effort while maximizing transparency and confidence throughout the
transportation journey.

---

### VI. Modular Domain-Driven Architecture

The platform SHALL be built as a collection of independently specifiable domains.

Every specification MUST focus on a single business capability or bounded context.

Large features MUST be decomposed into smaller specifications.

The platform architecture MUST support independent development, testing, deployment, and future
scaling.

No specification SHALL attempt to define or implement the entire platform.

---

### VII. Shared Foundations, Independent Applications

Fe El Seka consists of three platform applications: Passenger Application, Driver Application, and
Admin Panel.

All applications SHALL exist within a single monorepo and share common foundations where
appropriate.

Shared business models, APIs, authentication mechanisms, and reusable components MUST be
implemented once and reused across applications.

Duplication of shared functionality is prohibited unless explicitly justified.

---

## Technical Standards

### Approved Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python FastAPI |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth |
| Storage | Supabase Storage |
| Secrets Management | Supabase Vault |
| Geospatial Processing | PostGIS |
| Routing Infrastructure | OpenStreetMap (OSM), OSRM |

All specifications and implementations MUST align with the approved technology stack unless
formally amended.

---

### Architecture Standards

- Backend services MUST own business logic.
- Frontend applications are presentation and interaction layers only.
- Databases are the source of truth.
- APIs MUST be defined before frontend integrations.
- Services SHOULD be independently deployable where practical.
- AI capabilities MUST exist as dedicated services.
- Critical business rules MUST NOT exist exclusively in frontend applications.

---

### Data Standards

- UUID primary keys are required for all entities.
- Geospatial data MUST use appropriate spatial database types (PostGIS geometry/geography).
- Critical operational history MUST be preserved.
- Soft deletion is preferred for transactional entities.
- Sensitive information MUST be protected and access-controlled.
- National identification data MUST NOT be publicly exposed.

---

## Security & Privacy Requirements

### Identity & Verification

The platform MUST support robust identity verification mechanisms for all transportation
participants.

Verification systems MUST establish trust between passengers and drivers while protecting user
privacy.

---

### Data Protection

Sensitive information MUST be encrypted in transit and at rest.

Authentication MUST be managed through approved identity systems (Supabase Auth).

Secrets MUST be stored exclusively through approved secrets-management infrastructure (Supabase
Vault).

Least-privilege access principles MUST be enforced throughout the platform.

---

### Auditability

Critical platform actions MUST be traceable and auditable.

This includes, but is not limited to: verification activities, ride operations, booking operations,
financial operations, and administrative actions.

---

## Real-Time Transportation Requirements

The platform MUST support real-time transportation experiences.

Core real-time capabilities include:

- Live ride status updates
- Live location tracking
- ETA updates
- Ride progress monitoring

Real-time data access MUST respect privacy boundaries and transportation context.

Users MAY only access real-time information directly relevant to their transportation activities.

---

## Development Workflow Standards

### Specification-Driven Development

All significant work MUST begin with a specification.

Every specification MUST define:

- Business Objective
- Functional Requirements
- Non-Functional Requirements
- Acceptance Criteria
- Dependencies
- Out-of-Scope
- Technical Considerations

Implementation MUST follow approved specifications.

---

### Domain-Based Planning

Specifications, plans, and tasks MUST remain domain-focused.

Examples of domains include: Authentication, Verification, Ride Creation, Route Matching, Pricing,
Live Tracking, AI Services, Payments, and Administration.

Cross-domain implementations require explicit dependency management.

---

### Quality Standards

All implementations MUST:

- Be testable
- Be maintainable
- Follow established architectural patterns
- Support future scaling requirements
- Include appropriate documentation
- Avoid unnecessary complexity

Solutions MUST favor simplicity unless complexity is demonstrably justified.

---

## Governance

This Constitution is the highest authority governing Fe El Seka specifications, plans, tasks, and
implementations.

All future specifications MUST demonstrate compliance with this Constitution.

**Conflict Resolution Order**:

1. Constitution
2. Specification
3. Plan
4. Tasks
5. Implementation

**Amendment Procedure**: Constitutional amendments require documented justification, impact
analysis, approval by project leadership, and a version increment.

**Versioning Policy**:

- MAJOR: Backward-incompatible principle removal or redefinition.
- MINOR: New principle or section addition, or material expansion.
- PATCH: Clarifications, wording fixes, non-semantic refinements.

No specification, plan, or implementation may override constitutional principles without a formal
amendment.

**Version**: 1.0.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10
