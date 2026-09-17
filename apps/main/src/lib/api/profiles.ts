import type { Profile, ProfileSetup, ProfileUpdate, PublicProfile } from "@fe-el-seka/shared";
import { env } from "../env";

// Profile setup and onboarding are the first authenticated browser requests.
// Send them through the Next.js same-origin proxy so they are not exposed to a
// cross-origin preflight/edge-proxy failure between the app and FastAPI.
const base = typeof window === "undefined" ? env.serverApiUrl : "/api-proxy";
const NETWORK_RETRY_DELAY_MS = 400;

// A dropped response can happen after an idempotent profile write has already
// reached the API. Retrying once prevents onboarding from showing a generic
// browser "Failed to fetch" error and safely overwrites the same profile data
// (and the deterministic profile-photo object path).
async function fetchProfileWrite(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    await new Promise((resolve) => setTimeout(resolve, NETWORK_RETRY_DELAY_MS));
    try {
      return await fetch(url, init);
    } catch (retryError) {
      if (!(retryError instanceof TypeError)) throw retryError;
      // Never expose a browser implementation detail such as "Failed to
      // fetch" as the signup result. It gives the person no indication that
      // the save can simply be retried, and it masks the fact that the first
      // idempotent write may already have succeeded.
      throw {
        error: "network_error",
        message: "We couldn't reach the server. Please check your connection and try again.",
      };
    }
  }
}

// The authentication endpoint's `is_new_user` value can be stale if a prior
// setup request reached the API but its response was lost. The profile record
// itself is the source of truth for where an authenticated person belongs.
// If the API is temporarily unreachable, retain the auth response as a safe
// fallback so a genuine first-time user can still enter onboarding.
export async function hasProfile(token: string): Promise<boolean | null> {
  try {
    const res = await fetch(`${base}/api/profiles/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) return true;
    if (res.status === 404) return false;
  } catch {
    // The caller will use the sign-in response as a fallback.
  }
  return null;
}

export async function signedInRedirect(token: string, isNewUser: boolean): Promise<"/" | "/role-select"> {
  const profileExists = await hasProfile(token);
  if (profileExists !== null) return profileExists ? "/" : "/role-select";
  return isNewUser ? "/role-select" : "/";
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key ({"detail": {"error": ..., "message": ...}}) — unwrap it so
// callers can check err.error / err.message directly.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  try {
    const body = await res.json();
    if (body && typeof body === "object" && body.detail && typeof body.detail === "object") {
      return body.detail;
    }
    return body;
  } catch {
    return { message: `Server error (${res.status}). Please try again.` };
  }
}

export async function setupProfile(token: string, data: ProfileSetup): Promise<Profile> {
  const res = await fetch(`${base}/api/profiles/setup`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getMe(token: string): Promise<Profile> {
  const res = await fetch(`${base}/api/profiles/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function updateMe(token: string, data: ProfileUpdate): Promise<Profile> {
  let res: Response;
  try {
    res = await fetchProfileWrite(`${base}/api/profiles/me`, {
      method: "PUT",
      headers: authHeaders(token),
      body: JSON.stringify(data),
    });
  } catch (error) {
    const networkError = error as { error?: string };
    if (networkError.error !== "network_error") throw error;

    // A proxy may drop the response after the update has reached the API.
    // Confirming the persisted fields makes this idempotent onboarding write
    // complete instead of asking the user to submit the same form again.
    try {
      const saved = await getMe(token);
      const dateMatches = !data.date_of_birth || saved.date_of_birth === data.date_of_birth;
      if (
        (!data.display_name || saved.display_name === data.display_name) &&
        (!data.phone_number || saved.phone_number === data.phone_number) &&
        dateMatches &&
        (!data.gender || saved.gender === data.gender)
      ) {
        return saved;
      }
    } catch {
      // Surface the original connection error when persistence cannot be confirmed.
    }
    throw error;
  }
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getPublicProfile(token: string, userId: string): Promise<PublicProfile> {
  const res = await fetch(`${base}/api/profiles/${userId}/public`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function uploadPhoto(token: string, file: File): Promise<{ profile_photo_url: string }> {
  const form = new FormData();
  form.append("photo", file);
  const res = await fetchProfileWrite(`${base}/api/profiles/me/photo`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}
