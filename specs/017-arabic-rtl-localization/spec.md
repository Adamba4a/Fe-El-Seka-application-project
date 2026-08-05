# Feature Specification: Arabic & RTL Localization

**Feature Branch**: `017-arabic-rtl-localization`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Phase 14 — Localization: Full Arabic UI, RTL layout, bilingual language toggle for the Triplyy platform"

## Business Objective *(mandatory)*

Enable Triplyy's primarily Egyptian, Arabic-speaking user base to use the platform fully in Arabic
with a correctly mirrored right-to-left layout, while preserving English as a first-class alternative
via a simple language toggle. This removes the language barrier that currently limits adoption among
users who are not comfortable reading and transacting in English.

**Constitutional Domain**: Mobile-First User Experience (Principle V) / Localization

**Affected Applications**: Main App (Passenger + Driver)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the platform entirely in Arabic (Priority: P1)

A passenger or driver whose preferred language is Arabic opens Triplyy and finds every screen —
navigation, ride search, booking, ride management, notifications, and account settings — displayed
in Arabic with a right-to-left layout that reads naturally (menus, forms, ride cards, and directional
icons mirrored appropriately).

**Why this priority**: This is the core value of the feature — without full-screen Arabic coverage
and correct RTL mirroring, the feature delivers no usable value to Arabic-speaking users, who are the
majority of the target market.

**Independent Test**: Switch the app language to Arabic and complete a full ride search-to-booking
flow; every screen in the flow is in Arabic with correct RTL layout and no leftover English strings
or broken/mirrored-incorrectly UI elements.

**Acceptance Scenarios**:

1. **Given** a user has selected Arabic as their display language, **When** they navigate to any
   screen in the Main App, **Then** all UI text, labels, buttons, and system messages are displayed in
   Arabic.
2. **Given** a user has selected Arabic as their display language, **When** they view any screen,
   **Then** the layout direction is right-to-left, including navigation order, form field alignment,
   and directional icons (e.g., back/forward arrows).
3. **Given** a user has selected Arabic as their display language, **When** a new booking or ride
   status update is created, **Then** any push notification generated for that event is delivered in
   Arabic.

---

### User Story 2 - Switch language at any time (Priority: P2)

A user wants to change their display language (English ↔ Arabic) from within the app without losing
their place, restarting a booking in progress, or having to log out and back in.

**Why this priority**: A visible, always-available toggle is what makes the feature usable day to day
and lets users who are more comfortable switching between languages (a common pattern in Egypt) do so
without friction.

**Independent Test**: While on any screen (including mid-flow, e.g., an in-progress ride search),
toggle the language and confirm the current screen re-renders in the new language without loss of
navigation state or in-progress input.

**Acceptance Scenarios**:

1. **Given** a user is on any screen, **When** they select the language toggle, **Then** the entire
   app switches language and layout direction immediately without a full page reload losing their
   current screen context.
2. **Given** an authenticated user changes their language, **When** they log in again later on the
   same or a different device, **Then** the app opens in their previously selected language.
3. **Given** an unauthenticated visitor changes their language, **When** they return in a later
   session on the same device, **Then** the app remembers their last selected language for that
   device.

---

### User Story 3 - Locale-appropriate formatting and content (Priority: P3)

A user viewing dates, times, currency (EGP), and distances sees them formatted according to
conventions appropriate for their selected language, and any content the platform itself generates
(error messages, empty states, confirmation text) reads naturally in Arabic rather than as a literal
or awkward translation.

**Why this priority**: Correct formatting and natural phrasing are what make the Arabic experience
feel native rather than a mechanical overlay; this materially affects trust and usability but the
platform is still functional without polish on every edge case at first launch.

**Independent Test**: Review a set of representative screens (ride details, booking confirmation,
error/empty states) in Arabic and confirm dates, currency, and numbers are formatted per locale
convention and all copy reads as natural Arabic, not machine-literal translation.

**Acceptance Scenarios**:

1. **Given** a user has selected Arabic, **When** they view a ride's date, time, or fare, **Then**
   these values are formatted using Arabic-locale date/time conventions and EGP currency formatting.
2. **Given** a user has selected Arabic, **When** they encounter an error, empty state, or
   confirmation message, **Then** the message is a natural Arabic phrasing reviewed for tone, not a
   raw machine translation.

---

### Edge Cases

- What happens when a user has partially entered data in a form (e.g., ride search filters) and
  switches language mid-entry? The entered values MUST be preserved; only labels/UI chrome
  re-render in the new language/direction.
- How does the system handle a screen where translated Arabic text is significantly longer than the
  English source (common in Arabic translation) and could overflow or truncate UI elements?
- How does the system handle mixed-direction content, such as a Latin-script name or English street
  name appearing inside an otherwise Arabic, RTL-rendered screen?
- What happens when a new app screen or feature ships without an Arabic translation yet available
  (translation lag behind development)? The system MUST NOT display raw translation keys or blank
  text to the user.
- How does live ride tracking (map, live location) behave in RTL mode, given that maps themselves
  are not mirrored even when surrounding UI is?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support two display languages — English and Arabic — across all Passenger
  and Driver-facing screens in the Main App.
- **FR-002**: Users MUST be able to switch the display language from a visible, always-accessible
  control, from any screen, without needing to log out or restart the app.
- **FR-003**: When Arabic is selected, System MUST render the layout right-to-left, including
  navigation order, form alignment, ride cards, and directional icons; embedded map controls and
  map content are exempt from mirroring per standard mapping conventions.
- **FR-004**: System MUST persist an authenticated user's selected language preference to their
  account and apply it automatically on subsequent logins, regardless of device.
- **FR-005**: System MUST remember an unauthenticated visitor's last selected language for their
  current device/browser and apply it on return visits until they authenticate or change it again.
- **FR-006**: All static UI text — labels, buttons, navigation, form fields, validation messages,
  error messages, empty states, and confirmation dialogs — MUST have a reviewed Arabic translation;
  no screen may display a mix of Arabic and untranslated English strings.
- **FR-007**: System MUST format dates, times, and currency (EGP) according to the conventions of
  the user's selected language.
- **FR-008**: Push notifications (booking events, ride status changes, verification updates) MUST be
  sent in the recipient's selected display language.
- **FR-009**: System MUST NOT translate or alter user-generated content (e.g., driver notes, ride
  descriptions entered by users) — such content is displayed exactly as entered regardless of the
  viewer's selected language.
- **FR-010**: System MUST maintain full feature parity between the English and Arabic versions —
  every feature available in one language MUST be available and fully functional in the other.
- **FR-011**: System MUST gracefully handle UI text that has not yet been translated into Arabic
  (e.g., a newly shipped screen) by falling back to the English source string rather than showing a
  blank space or a raw translation key.
- **FR-012**: System MUST preserve user-entered form data when the display language is switched
  mid-entry.

### Key Entities *(include if feature involves data)*

- **User Language Preference**: The display language (English or Arabic) associated with a user
  account, persisted so it can be applied automatically across sessions and devices.
- **Translated Content Bundle**: The set of UI strings maintained per supported language that every
  screen draws from; conceptually a content asset rather than transactional data, but subject to the
  same completeness and fallback requirements as any other user-facing content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of screens in the Main App (Passenger + Driver) render with no untranslated
  English text when Arabic is selected.
- **SC-002**: Users can switch the app's display language in under 2 seconds and without losing their
  current screen or in-progress input.
- **SC-003**: A returning authenticated user's app opens in their previously selected language on
  first paint, with no visible language flash or flicker, in at least 99% of sessions.
- **SC-004**: At least 90% of Arabic-language users surveyed report the Arabic experience feels
  natural (not machine-translated) rather than awkward or literal.
- **SC-005**: Zero critical layout defects (overlapping, truncated, or unreadable elements) are
  observed across primary flows (search, booking, ride management, notifications) when tested in
  Arabic/RTL mode.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Language/direction switching MUST complete and re-render the current screen within 2
  seconds under normal network conditions.
- **NFR-002**: Loading translated content MUST NOT add more than 10% to a screen's baseline load time
  compared to the English-only experience.
- **NFR-003**: The translation content system MUST support adding or updating strings without
  requiring a full application redeployment for copy-only changes, to keep translation quality
  maintainable over time.
- **NFR-004**: RTL layout support MUST cover 100% of Passenger and Driver-facing screens at launch —
  no screen may be English-only or left-to-right-only.

---

## Dependencies *(mandatory)*

- **Internal**: Passenger Experience, Ride Management, Real-Time Transportation, and Financial
  System domains — every existing screen and notification template in these domains must be
  inventoried and translated as part of this feature.
- **Internal**: User profile/account system — must be extended to store a per-user language
  preference.
- **External**: Push notification delivery (FCM) — notification templates must support per-language
  content selection at send time.
- **Data**: None beyond the addition of a language-preference attribute to the existing user profile
  record.

---

## Out-of-Scope

- Admin Panel localization — the Admin Panel remains English-only for this iteration; it is an
  internal operations tool and is not part of this feature's scope.
- Machine-translating or otherwise altering user-generated content (ride notes, descriptions, chat
  text, etc.) — such content is always shown as originally entered.
- Support for languages other than English and Arabic.
- Translating third-party map data or map provider UI (street names, POI labels) — only Triplyy's own
  UI chrome is in scope.
- Voice, audio, or accessibility-reader localization beyond standard text-based translation.

---

## Technical Considerations

- RTL support must be applied consistently across the shared component library so both current and
  future screens inherit correct mirroring by default, rather than requiring per-screen RTL patches.
- Route and turn-by-turn map content follows standard mapping conventions and is not mirrored even
  when the surrounding app shell is RTL (Principle II — routing intelligence remains sourced from
  OSRM/PostGIS regardless of display language).
- Notification templates (FCM) must be authored per-language and selected at send time based on the
  recipient's stored language preference.
- Numeric values are displayed using Western Arabic numerals (0–9) in both language modes, consistent
  with common digital-Egyptian convention, even though other Arabic text is right-to-left.

---

## Assumptions

- Egypt is the primary market, so Arabic and English are sufficient; no other languages are required
  for this iteration.
- Numerals are displayed in Western Arabic digit form (0–9) regardless of selected language, per
  common Egyptian digital convention.
- Professional/reviewed human translation (not raw machine translation) is expected for all
  static UI copy, consistent with the "natural, not literal" experience described in User Story 3.
- The Admin Panel's internal staff users are comfortable operating in English, so it is excluded from
  this feature's scope (see Out-of-Scope).
- First-time, unauthenticated visitors default to Arabic, reflecting the primary Egyptian market,
  with the option to switch to English at any time; authenticated users always see their stored
  preference.
- Existing UI components (shadcn/ui + Tailwind CSS) can be adapted for RTL support without requiring
  a change to the underlying component library.
