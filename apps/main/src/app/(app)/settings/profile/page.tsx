"use client";

import { useEffect, useState } from "react";
import { ProfileEditor } from "./ProfileEditor";
import type { Profile, Vehicle, VehicleUpdateRequestRecord } from "@fe-el-seka/shared";

export default function SettingsProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [pendingUpdate, setPendingUpdate] = useState<VehicleUpdateRequestRecord | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        // Get the access token from the server — browser client can't read the
        // session cookies because they're named after the Docker-internal
        // Supabase URL, not the public one NEXT_PUBLIC_SUPABASE_URL points to.
        const sessionRes = await fetch("/settings/session");
        const sessionData = await sessionRes.json().catch(() => null);
        const token: string | undefined = sessionData?.access_token;

        if (!token) {
          setErrorMsg("Session expired. Please sign in again.");
          return;
        }

        setAccessToken(token);

        const profileRes = await fetch("/api/profiles/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!profileRes.ok) {
          const body = await profileRes.text().catch(() => "");
          setErrorMsg(`Could not load profile (${profileRes.status}): ${body}`);
          return;
        }

        const profileData = (await profileRes.json()) as Profile;
        setProfile(profileData);

        if (profileData.role === "driver") {
          const [vehicleRes, updateRes] = await Promise.all([
            fetch("/api/vehicles/me", { headers: { Authorization: `Bearer ${token}` } }),
            fetch("/api/vehicles/me/update-request", { headers: { Authorization: `Bearer ${token}` } }),
          ]);
          if (vehicleRes.ok) setVehicle((await vehicleRes.json()) as Vehicle);
          if (updateRes.ok) setPendingUpdate((await updateRes.json()) as VehicleUpdateRequestRecord);
        }
      } catch (err: unknown) {
        setErrorMsg(`Unexpected error: ${String(err)}`);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return (
      <main className="max-w-sm mx-auto p-6 space-y-4">
        <div className="h-8 bg-gray-200 rounded w-40 animate-pulse" />
        <div className="h-24 bg-gray-200 rounded animate-pulse" />
        <div className="h-12 bg-gray-200 rounded animate-pulse" />
      </main>
    );
  }

  if (errorMsg) {
    return (
      <main className="max-w-sm mx-auto p-6 space-y-4">
        <div className="flex items-center gap-3">
          <a href="/rides" className="text-gray-500 hover:text-gray-700 text-lg">←</a>
          <h1 className="text-xl font-bold">Profile</h1>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 text-sm font-medium">Could not load profile</p>
          <p className="text-red-600 text-xs mt-1 break-all">{errorMsg}</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium"
        >
          Retry
        </button>
      </main>
    );
  }

  if (!profile || !accessToken) return null;

  return (
    <ProfileEditor
      initialProfile={profile}
      initialVehicle={vehicle}
      initialPendingUpdate={pendingUpdate}
      accessToken={accessToken}
    />
  );
}
