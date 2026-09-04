const STORAGE_KEY = "triplyy_device_id";

// Stable per-install identifier sent as X-Device-Id on trust-relevant
// requests (signup, login, ride posting, booking creation) — never tied to
// hardware serials or advertising IDs, just a locally-generated UUID. Returns
// null (never blocks the caller) when running server-side or when storage is
// unavailable (private browsing, storage disabled).
export function getDeviceId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) return existing;
    const generated = crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, generated);
    return generated;
  } catch {
    return null;
  }
}
