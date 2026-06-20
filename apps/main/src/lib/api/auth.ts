import type { SessionResponse } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

export async function requestOtp(email: string): Promise<{ message: string; expires_in_seconds: number }> {
  const res = await fetch(`${base}/api/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function verifyOtp(email: string, otp: string): Promise<SessionResponse> {
  const res = await fetch(`${base}/api/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, otp }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function refreshToken(refresh_token: string): Promise<{ access_token: string; expires_in: number }> {
  const res = await fetch(`${base}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function signOut(accessToken: string): Promise<void> {
  await fetch(`${base}/api/auth/sign-out`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
