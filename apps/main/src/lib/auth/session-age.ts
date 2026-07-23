// Absolute session cap enforced by middleware.ts on top of Supabase's own
// (sliding, effectively unbounded) refresh-token rotation. See middleware.ts
// for how this cookie is stamped and checked.
export const SESSION_STARTED_COOKIE = "session_started_at";
export const SESSION_MAX_AGE_MS = 24 * 60 * 60 * 1000;
// Cookie itself must outlive the session cap so the timestamp is still
// readable when we check it; the value inside is what actually gates access.
export const SESSION_STARTED_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 60;
