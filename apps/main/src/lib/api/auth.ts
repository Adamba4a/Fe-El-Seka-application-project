import type { SessionResponse } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

// A non-JSON body (e.g. nginx/proxy HTML error pages) means the request never
// reached the API — surface a readable message instead of a JSON parse error.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  if (!res.headers.get("content-type")?.includes("application/json")) {
    return { message: `Server error (${res.status}). Please try again.` };
  }
  try {
    const body = await res.json();
    // FastAPI's default HTTPException handler wraps our {error, message} dict
    // under a "detail" key ({"detail": {"error": ..., "message": ...}}) —
    // unwrap it so callers can check err.error / err.message directly.
    if (body && typeof body === "object" && body.detail && typeof body.detail === "object") {
      return body.detail;
    }
    return body;
  } catch {
    return { message: `Server error (${res.status}). Please try again.` };
  }
}

export async function requestOtp(email: string): Promise<{ message: string; expires_in_seconds: number }> {
  const res = await fetch(`${base}/api/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function verifyOtp(email: string, otp: string): Promise<SessionResponse> {
  const res = await fetch(`${base}/api/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, otp }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function signInWithPassword(email: string, password: string): Promise<SessionResponse> {
  const res = await fetch(`${base}/api/auth/sign-in-with-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function setPassword(accessToken: string, newPassword: string): Promise<void> {
  const res = await fetch(`${base}/api/auth/password`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
}

export async function refreshToken(refresh_token: string): Promise<{ access_token: string; expires_in: number }> {
  const res = await fetch(`${base}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function signOut(accessToken: string): Promise<void> {
  await fetch(`${base}/api/auth/sign-out`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
