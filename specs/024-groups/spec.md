# Feature Specification: Groups

**Feature Branch**: `024-groups`

**Created**: 2026-08-26

**Status**: Draft

**Input**: User description: "Groups (feature 024-groups) — Drivers post rides scoped to a 'group' instead of only the general city-wide feed. A group is a community of drivers and passengers interested in a particular kind of trip pattern — e.g. a specific route corridor (like 'El Shorouk / Badr to Sheikh Zayed'), or a shared affiliation (same company, same university). Drivers within a group post rides as normal (existing ride creation flow, just scoped to the group); passengers within the group browse/search and book those rides through the existing booking flow. No new booking mechanics — groups are a discovery/scoping layer on top of what already exists. Three group types: general/interest (open, route-based, anyone can create), company (verified via work email), university (verified via school email). Both drivers and passengers can discover groups via search/directory (by name, type, route tags) or join via a shareable invite link — both paths lead to the same join flow and gating rules; an invite link never bypasses verification. Company/university verification is domain-gated email OTP: user proves mailbox ownership via a one-time code; the domain must not be a public/personal email provider (gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com, protonmail.com, etc.); any other domain is accepted automatically once OTP succeeds — no manual admin review step. This is a soft 'domain-verified' signal layered on top of the platform's already-mandatory National ID identity verification, not an employment/enrollment verification claim. Basic anti-abuse: rate-limit how many distinct users can be the first to register a brand-new, previously-unseen domain within a time window. Out of scope for v1: live chat/messaging between members, AI-driven recommendations for rides or groups (deferred to a later spec, 025-recommendations), paid third-party KYC/employment-verification integration."

---

## Clarifications

### Session 2026-08-26

- Q: When a company/university domain is verified for the first time, how does the resulting group get its display name? → A: Auto-derived from the domain (e.g., `acmecorp.com` → "Acmecorp"), no manual naming step for the first verifier.
- Q: Can a single ride be scoped to multiple groups simultaneously, or exactly one group per ride? → A: Exactly one group per ride (or unscoped, visible on the general feed).
- Q: Do invite links expire automatically, stay permanently valid, or are they single-use? → A: Permanent and reusable until the owner explicitly revokes/regenerates them, invalidating the old link.

---

## Business Objective *(mandatory)*

Let drivers and passengers discover and transact within focused communities — a route corridor, a shared workplace, or a shared university — instead of only the undifferentiated city-wide feed, increasing match relevance and rider confidence without introducing any new ride-creation, search, or booking mechanism. Groups are a discovery and trust-scoping layer on top of the existing ride lifecycle.

**Constitutional Domain**: Ride Grouping (Principle I extension; Principle IV names "Ride Grouping" as an AI-enhanced domain — this spec establishes the deterministic community/membership foundation that a later AI-driven recommendation spec builds on)

**Affected Applications**: Main App (Passenger experience + Driver experience). Admin Panel and AI services are not affected by this spec.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and Discover a General Group (Priority: P1)

A driver who regularly travels the El Shorouk/Badr → Sheikh Zayed corridor creates a general/interest group for that route. Other drivers and passengers who make similar trips find the group by searching the group directory by name or route tag, and see enough about it (name, description, route tags, member count) to decide whether to join.

**Why this priority**: Without the ability to create and discover a group, nothing else in this feature has an audience. This is the foundation every other story depends on.

**Independent Test**: Can be fully tested by creating a general group with a name and route tags, then searching the directory from a different account and confirming the group is found and its public details are visible — delivers standalone value (community discovery) even before any ride or verification logic exists.

**Acceptance Scenarios**:

1. **Given** a logged-in, org-email-verified user, **When** they create a group with a name, type ("general"), description, and one or more route tags, **Then** the group exists and that user becomes its owner and first member.
2. **Given** an existing general group, **When** another user searches the group directory by a matching name, type, or route tag, **Then** the group appears in results with its name, type, description, route tags, and member count visible, without requiring membership.
3. **Given** a group directory search with no matching groups, **When** a user searches, **Then** the system clearly indicates no matches and offers to create a new group.

---

### User Story 2 - Post and Book Rides Within a Group (Priority: P1)

A driver who is a member of a group posts a ride the same way they always do, but scopes it to that group. Passengers who are members of that group see the ride when browsing the group and book it through the platform's normal booking flow. The ride does not appear in the general city-wide feed for non-members.

**Why this priority**: This is the entire point of the feature — without ride posting and booking scoped to group membership, groups are just an empty directory. Depends on User Story 1 (a group must exist to post into).

**Independent Test**: Can be fully tested by having a group-member driver post a ride scoped to the group, then confirming a group-member passenger can see and book it via the existing booking flow, while a non-member cannot see it in that group or in the general feed.

**Acceptance Scenarios**:

1. **Given** a driver who is a member of a group, **When** they create a ride and scope it to that group, **Then** the ride is created through the platform's existing ride-creation flow and is visible only within that group's ride listing.
2. **Given** a passenger who is a member of the group, **When** they open the group's ride listing, **Then** they see all active rides posted to that group and can book any of them using the existing booking flow, with no new booking steps.
3. **Given** a user who is not a member of the group, **When** they search the platform's general city-wide feed or attempt to view the group's ride listing directly, **Then** the group-scoped rides are not shown and the ride listing is inaccessible.
4. **Given** a driver posts the same trip pattern regularly, **When** they create a ride, **Then** they may choose to scope it to a group or leave it unscoped (visible on the general feed as today) — scoping is optional per ride.

---

### User Story 3 - Join a Group via Invite Link (Priority: P2)

A group owner shares a link to their group (e.g., in a messaging app outside the platform). A driver or passenger who receives the link opens it and lands directly on the group's join screen, going through the same join rules as if they had found the group via search.

**Why this priority**: Search/directory discovery (US1) covers organic discovery; invite links cover the common real-world case of a group being spread by word of mouth. Independently valuable but secondary to the directory existing at all.

**Independent Test**: Can be fully tested by generating an invite link from an existing group and opening it from a fresh account, confirming it deep-links to the same join screen and enforces the same gating rules as directory-based joining (verified separately for each group type in US1/US4).

**Acceptance Scenarios**:

1. **Given** an existing group, **When** its owner requests a shareable invite link, **Then** the system produces a link that, when opened, takes any user directly to that group's join screen.
2. **Given** a general/interest group's invite link, **When** a new user opens it, **Then** they can join immediately (subject to the same org-email-verification floor required platform-wide) with no additional gate beyond what directory-based joining requires.
3. **Given** a company or university group's invite link, **When** a new user opens it, **Then** they must still complete domain-gated email verification (User Story 4) before becoming a member — the link does not bypass that gate.
4. **Given** an invite link, **When** it is opened by a user who is already a member, **Then** the system shows they are already a member rather than duplicating membership.

---

### User Story 4 - Join a Company or University Group via Domain-Verified Email (Priority: P2)

A user wants to join or create a group scoped to their workplace or university. They enter their work/school email address, receive a one-time code, and confirm it. Once confirmed, they're a "domain-verified" member of that company/university's group. Any other user who later verifies an email on that same domain is automatically eligible to join without any additional review step.

**Why this priority**: This unlocks the two group types (company, university) that carry the platform's strongest trust signal beyond general groups, but the platform is still useful via general groups (US1-3) without it — hence P2, not P1.

**Independent Test**: Can be fully tested end-to-end by attempting verification with a public-provider email (must be rejected before an OTP is even sent), then completing verification with a valid organizational email (OTP sent, confirmed, group membership granted), and confirming a second user on the same domain joins without any extra step.

**Acceptance Scenarios**:

1. **Given** a user attempting to create or join a company/university group, **When** they submit an email address whose domain is on the public-provider blocklist (e.g., gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com, protonmail.com), **Then** the system rejects it immediately with a clear message, and no OTP is sent.
2. **Given** a user submits an email address on a domain not on the blocklist, **When** they request verification, **Then** the system sends a one-time code to that address.
3. **Given** a user who received a one-time code, **When** they enter the correct code within its validity window, **Then** their email/domain is confirmed and they become a "domain-verified" member of the group associated with that domain (an existing group if one already exists for that domain, or a newly created one if they are the first).
4. **Given** an incorrect or expired code, **When** the user submits it, **Then** verification fails with a clear error and the user may request a new code, subject to standard rate limiting.
5. **Given** a domain that has already been successfully verified by at least one prior user, **When** a second user verifies an email on that same domain, **Then** they join the existing group automatically with no manual review or approval step from anyone.
6. **Given** a domain that has never been used before on the platform, **When** enough distinct users attempt to be the "first" verifier for new, never-seen domains within a short time window, **Then** the system throttles further first-time domain registrations until the window passes, to blunt automated spam group creation.
7. **Given** a successfully domain-verified group, **When** its membership or details are displayed, **Then** the platform labels it as "domain-verified," never as "employer-verified" or "verified employee."

---

### User Story 5 - Leave and Manage Group Membership (Priority: P3)

A member who no longer wants to be part of a group leaves it. A group owner can remove a disruptive member. Basic housekeeping so groups remain a stable, well-kept community over time.

**Why this priority**: Necessary for long-term usability but the feature delivers its core value (US1-4) without it on day one; a reasonable v1 could ship without owner-removal and add it shortly after.

**Independent Test**: Can be fully tested by having a member leave a group and confirming they lose access to that group's ride listing, and by having an owner remove another member and confirming the same outcome.

**Acceptance Scenarios**:

1. **Given** a member of a group, **When** they choose to leave, **Then** they immediately lose access to that group's ride listing and are no longer counted as a member.
2. **Given** a group owner, **When** they remove another member, **Then** that member loses access the same way as if they had left voluntarily.
3. **Given** a group's owner tries to leave their own group, **When** other members remain, **Then** the system requires them to either transfer ownership to another member or confirms the group will have no owner going forward, rather than silently leaving the group ownerless.

---

### Edge Cases

- What happens when a driver who posted rides into a group later leaves or is removed from it? (Their already-posted, still-active rides remain visible to the group; they can no longer post new rides into it without rejoining.)
- What happens when a group has zero members other than its creator? (Groups are fully functional with a single member; the creator can post/browse immediately.)
- What happens when a user tries to verify an email domain that collides with an existing group's domain but under a different group *type* (e.g., someone tries to register a university group for a domain already claimed as a company group)? (A domain maps to exactly one company/university group; the first successful verification on a domain fixes its type going forward.)
- What happens when someone requests many OTP codes in a row for the same or different emails? (Standard rate limiting applies, matching the platform's existing phone OTP throttling pattern.)
- What happens to a group's already-posted rides if the group is deleted or archived? (Existing rides keep running through their normal ride lifecycle to completion or cancellation; the group stops accepting new members or new ride postings.)
- What happens when a non-member tries to access a group's ride listing or invite-link join screen for a company/university group without ever having entered an email? (They are shown the verification step; they cannot see any ride listing until domain verification succeeds.)
- What happens when someone opens a revoked or regenerated invite link? (It no longer resolves to the join screen; the group's already-existing members are unaffected.)
- What happens when a passenger who is a member of multiple groups searches? (Group membership does not change the general city-wide feed; each group's rides are seen only within that group's own listing, viewed one group at a time.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an org-email-verified user (Spec 025) to create a general group by providing a name, a description, and one or more route tags. Company and university groups are not created through this manual form — they come into existence via domain verification (see FR-010–FR-013).
- **FR-002**: System MUST make the creator of a group its owner and first member at creation time.
- **FR-003**: System MUST let any org-email-verified user (driver or passenger) search/browse a group directory by name, type, and route tags, and see each matching group's name, type, description, route tags, and member count without requiring membership.
- **FR-004**: System MUST let a group owner generate a shareable invite link that deep-links directly to that group's join screen. The link MUST remain permanently valid and reusable by any number of users until the owner explicitly revokes or regenerates it, at which point the previous link MUST stop working.
- **FR-005**: System MUST route both directory-based joining and invite-link-based joining through the same join flow and the same gating rules for a given group; an invite link MUST NOT bypass any verification a directory join would require.
- **FR-006**: System MUST let a driver who is a member of a group create a ride scoped to that group, using the platform's existing ride-creation flow.
- **FR-007**: System MUST make group-scoped rides visible only to members of that group, and MUST exclude them from the platform's general city-wide ride feed and search.
- **FR-008**: System MUST let a driver choose, per ride, whether to scope it to exactly one group or leave it unscoped on the general feed; a ride MUST NOT be scoped to more than one group at a time.
- **FR-009**: System MUST let a passenger who is a member of a group browse that group's active rides and book any of them through the platform's existing booking flow, with no additional booking steps introduced by group membership.
- **FR-010**: System MUST require, for joining or creating a company or university group, that the user submit an email address and confirm a one-time code sent to that address before membership is granted.
- **FR-011**: System MUST maintain a blocklist of public/personal email provider domains (at minimum: gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com, protonmail.com) and MUST reject any company/university verification attempt using an email on a blocklisted domain before sending any code.
- **FR-012**: System MUST accept any non-blocklisted domain automatically once the one-time code is confirmed, without any manual administrator approval step.
- **FR-013**: System MUST associate each verified non-blocklisted domain with exactly one company/university group; the first successful verification on a domain determines that group's existence and type, and every subsequent user who verifies an email on the same domain MUST join that same group automatically. The group's display name MUST be auto-derived from the domain (e.g., `acmecorp.com` → "Acmecorp") at creation, with no manual naming step required from the first verifier.
- **FR-014**: System MUST rate-limit how many distinct users can be the first to successfully register a previously-unseen domain within a given time window, to deter spam creation of fake organization groups.
- **FR-015**: System MUST label company/university group verification to users as "domain-verified," and MUST NOT represent it as employment or enrollment verification.
- **FR-016**: System MUST NOT require National ID identity verification (Spec 021) for any user to post or book a ride, group-scoped or otherwise — National ID verification is no longer a mandatory gate anywhere on the platform (legal constraint); org-email verification (Spec 025) is the sole trust-floor requirement for group actions.
- **FR-017**: System MUST let a member leave a group, immediately revoking their access to that group's ride listing and posting ability.
- **FR-018**: System MUST let a group owner remove another member, with the same effect as that member leaving voluntarily.
- **FR-019**: System MUST prevent a group's owner from leaving while other members remain unless ownership is first transferred to another member.
- **FR-020**: System MUST rate-limit one-time code requests per user/email to prevent abuse, consistent with the platform's existing phone OTP throttling pattern.
- **FR-021**: System MUST retain a group's already-posted, still-active rides through their normal lifecycle if the group is later deleted or archived, while preventing new members or new ride postings from that point on.

### Key Entities *(include if feature involves data)*

- **Group**: A named community with a type (general, company, or university), description, optional route tags, an owner, a member list, and — for company/university groups — an associated verified email domain. Rides may be scoped to a group.
- **Group Membership**: The relationship between a user and a group, including role (owner vs. member) and, for company/university groups, the domain-verification record that granted access.
- **Group Invite Link**: A shareable token that resolves to a specific group's join screen, permanently valid and reusable by multiple users until the owner revokes or regenerates it, subject to the same gating rules as directory-based joining.
- **Domain Verification**: A record of a user proving control of an email address on a given domain via one-time code, used to grant "domain-verified" status for a company/university group and to determine which group a domain maps to.
- **Ride (existing entity, extended)**: Gains an optional association to at most one group, scoping its visibility to that group's members instead of the general feed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can create a new group and obtain a shareable invite link in under 1 minute.
- **SC-002**: A user can find a relevant group through directory search in three or fewer steps from the group directory's entry point.
- **SC-003**: A legitimate company/university email verification (code sent to code confirmed) completes in under 2 minutes end-to-end for the user.
- **SC-004**: 100% of verification attempts using a blocklisted public email provider are rejected before any one-time code is sent.
- **SC-005**: 100% of group-scoped rides are absent from the general city-wide feed for users who are not members of that group.
- **SC-006**: A group member can go from opening the group to completing a booking on a ride within it using no more steps than booking a ride from the general feed today.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Group directory search MUST return results within the same performance envelope as the platform's existing ride search (interactive, sub-second perceived response under normal load).
- **NFR-002**: One-time code delivery MUST typically arrive within a timeframe consistent with the platform's existing phone OTP delivery experience.
- **NFR-003**: Domain-verification records and group membership data MUST be protected with the same least-privilege access controls as other identity-related data on the platform.
- **NFR-004**: The public-provider domain blocklist MUST be maintainable (additions/removals) without requiring a full application deployment.
- **NFR-005**: The new-domain rate-limit threshold MUST be configurable without requiring a full application deployment, matching the pattern already used for other platform-wide anti-abuse thresholds.

---

## Dependencies *(mandatory)*

- **Internal**: Ride Creation domain (rides gain an optional group scope); Passenger/Driver ride search and booking domains (existing flows are reused, filtered by group); Org-Email Verification domain (Spec 025 — the platform's sole trust-floor prerequisite for ride participation; National ID verification, Spec 021, is no longer a gate anywhere on the platform); the platform's existing one-time-code (OTP) delivery mechanism, extended to email in addition to phone.
- **External**: An email delivery capability able to send one-time verification codes to arbitrary external domains.
- **Data**: No new external data dependency; uses the platform's existing PostgreSQL database.

---

## Out-of-Scope

- Live chat or messaging between group members — this is a ride-discovery feature, not a messaging product.
- AI-driven recommendations for rides or groups (which groups or rides to suggest to a user) — deferred to a follow-on specification (025-recommendations) that builds on this one.
- Paid third-party KYC or employment/enrollment verification integrations — domain-gated email OTP is the full extent of company/university verification.
- Any manual administrative review or approval queue for new company/university domains.
- Changes to the ride-creation, search, or booking mechanics themselves — groups only add a scoping/visibility layer on top of what exists today.

---

## Technical Considerations

- Group-scoped ride visibility should extend the existing ride search/listing logic with a group filter rather than introducing a parallel ride-discovery system, per Principle VI (modular, non-duplicative architecture).
- Email one-time-code verification should reuse the pattern and infrastructure already established for phone OTP verification rather than introducing a separate verification mechanism.
- The public-provider domain blocklist and the new-domain rate-limit threshold should be stored as configurable platform settings (not hardcoded), consistent with how other admin-configurable thresholds are already handled elsewhere on the platform.
- Domain-to-group mapping must enforce a uniqueness constraint (one non-blocklisted domain → exactly one company/university group) to prevent duplicate or conflicting groups for the same organization.
- This spec intentionally excludes AI; Principle IV names "Ride Grouping" as an AI-enhanced domain, and this specification is the deterministic membership/community foundation that a later AI-driven recommendation spec is expected to build on.

---

## Assumptions

- Group-scoped rides are visible only within their group (not additionally surfaced in the general city-wide feed); this preserves the exclusivity that makes company/university groups meaningful and matches the "discovery/scoping layer" framing of the feature.
- A general/interest group's route tags are free-form descriptive text for v1, not a fixed geofence or enforced route boundary — route intelligence (OSRM/PostGIS overlap) is not required to gate group membership itself, only to power future recommendation work (out of scope here).
- A user may belong to any number of groups simultaneously; there is no exclusivity constraint between groups.
- A driver must be a member of a group before posting a ride scoped to it; a passenger must be a member before viewing or booking a group's ride listing.
- Group directory metadata (name, type, description, route tags, member count) is visible to any org-email-verified platform user, regardless of membership; only the actual ride listing requires membership to view.
- The platform already has (or can straightforwardly extend) an email-sending capability suitable for one-time codes, based on the existing phone OTP and transactional-notification patterns already in production.
- Group deletion/archival is a soft-deletion, consistent with the platform's existing data standard for transactional entities.
