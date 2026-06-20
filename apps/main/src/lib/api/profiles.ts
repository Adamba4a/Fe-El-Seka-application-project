import type { Profile, ProfileSetup, ProfileUpdate } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function setupProfile(token: string, data: ProfileSetup): Promise<Profile> {
  const res = await fetch(`${base}/api/profiles/setup`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getMe(token: string): Promise<Profile> {
  const res = await fetch(`${base}/api/profiles/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function updateMe(token: string, data: ProfileUpdate): Promise<Profile> {
  const res = await fetch(`${base}/api/profiles/me`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function uploadPhoto(token: string, file: File): Promise<{ profile_photo_url: string }> {
  const form = new FormData();
  form.append("photo", file);
  const res = await fetch(`${base}/api/profiles/me/photo`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
