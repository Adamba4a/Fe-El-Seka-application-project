import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { env } from "@/lib/env";
import { ProfileEditor } from "./ProfileEditor";
import type { Profile, Vehicle, VehicleUpdateRequestRecord } from "@fe-el-seka/shared";

export const dynamic = "force-dynamic";

async function apiFetch<T>(path: string, token: string): Promise<T | null> {
  try {
    const res = await fetch(`${env.apiUrl}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export default async function SettingsProfilePage() {
  const supabase = createClient();

  // getUser() validates with the auth server — uses cookie session, never localStorage
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // getSession() returns the (possibly just-refreshed) in-memory session
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) redirect("/login");

  // FastAPI uses service-role key (bypasses RLS) and generates signed photo URLs
  const profile = await apiFetch<Profile>("/api/profiles/me", token);
  if (!profile) redirect("/");

  let vehicle: Vehicle | null = null;
  let pendingUpdate: VehicleUpdateRequestRecord | null = null;

  if (profile.role === "driver") {
    [vehicle, pendingUpdate] = await Promise.all([
      apiFetch<Vehicle>("/api/vehicles/me", token),
      apiFetch<VehicleUpdateRequestRecord>("/api/vehicles/me/update-request", token),
    ]);
  }

  return (
    <ProfileEditor
      initialProfile={profile}
      initialVehicle={vehicle}
      initialPendingUpdate={pendingUpdate}
    />
  );
}
