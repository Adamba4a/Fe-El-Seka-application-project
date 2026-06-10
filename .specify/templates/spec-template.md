# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`

**Created**: [DATE]

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

## Business Objective *(mandatory)*

<!--
  ACTION REQUIRED: State the single business goal this feature serves.
  Reference the relevant constitutional domain (e.g., Authentication, Ride Creation, Route Matching).
-->

[One or two sentences describing the business goal and which platform application(s) it affects.]

**Constitutional Domain**: [e.g., Authentication / Ride Creation / Route Matching / Pricing / ...]

**Affected Applications**: [Passenger App / Driver App / Admin Panel / Shared]

---

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- What happens when [boundary condition]?
- How does system handle [error scenario]?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST [specific capability, e.g., "allow users to create accounts"]
- **FR-002**: System MUST [specific capability, e.g., "validate email addresses"]
- **FR-003**: Users MUST be able to [key interaction, e.g., "reset their password"]
- **FR-004**: System MUST [data requirement, e.g., "persist user preferences"]
- **FR-005**: System MUST [behavior, e.g., "log all security events"]

*Example of marking unclear requirements:*

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]
- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]

### Key Entities *(include if feature involves data)*

- **[Entity 1]**: [What it represents, key attributes without implementation]
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"]
- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"]
- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"]
- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"]

## Non-Functional Requirements *(mandatory)*

<!--
  ACTION REQUIRED: Define performance, security, scalability, and reliability requirements.
  These must be measurable and technology-aware but implementation-agnostic.
-->

- **NFR-001**: [Performance, e.g., "API endpoints MUST respond within 200ms at p95 under normal load"]
- **NFR-002**: [Security, e.g., "All data in transit MUST be encrypted via TLS 1.2+"]
- **NFR-003**: [Scalability, e.g., "Service MUST support 10,000 concurrent users without degradation"]
- **NFR-004**: [Availability, e.g., "Feature MUST be available 99.9% of the time"]

---

## Dependencies *(mandatory)*

<!--
  ACTION REQUIRED: List upstream features, services, or specs this feature depends on.
  Cross-domain dependencies require explicit management per the constitution.
-->

- **Internal**: [e.g., "Authentication domain — users must be authenticated before accessing this feature"]
- **External**: [e.g., "OSRM routing service must be operational for route calculations"]
- **Data**: [e.g., "Requires PostGIS extension enabled on the database"]

---

## Out-of-Scope

<!--
  ACTION REQUIRED: Explicitly state what this specification does NOT cover.
  This prevents scope creep and clarifies domain boundaries.
-->

- [e.g., "Payment processing — covered by the Payments domain specification"]
- [e.g., "Push notifications — out of scope for this iteration"]

---

## Technical Considerations

<!--
  ACTION REQUIRED: Note any technical constraints, risks, or architectural decisions
  relevant to implementation. Reference the approved technology stack.
-->

- [e.g., "Route calculations must use OSRM, not straight-line distance (Principle II)"]
- [e.g., "Geospatial fields must use PostGIS geometry types, not plain lat/lng columns"]
- [e.g., "AI-enhanced components must be implemented as dedicated services (Principle IV)"]

---

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- [Assumption about target users, e.g., "Users have stable internet connectivity"]
- [Assumption about scope boundaries, e.g., "Mobile support is out of scope for v1"]
- [Assumption about data/environment, e.g., "Existing authentication system will be reused"]
- [Dependency on existing system/service, e.g., "Requires access to the existing user profile API"]
