"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@supabase/ssr";
import { suspend, reinstate } from "@/lib/api/admin-users";
import { UserActionPanel } from "@/components/users/UserActionPanel";

const sb = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

interface Profile {
  id: string;
  display_name: string;
  email: string;
  role: string;
  verification_status: string;
  is_submission_locked: boolean;
}

export default function UserDetailPage({ params }: { params: { user_id: string } }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    const { data, error: err } = await sb
      .from("profiles")
      .select("id, display_name, email, role, verification_status, is_submission_locked")
      .eq("id", params.user_id)
      .single();
    if (err || !data) { setError("User not found"); return; }
    setProfile(data as Profile);
  }

  useEffect(() => { load(); }, [params.user_id]);

  async function handleSuspend(userId: string, reason: string) {
    const token = await getToken();
    await suspend(token, userId, reason);
    await load();
  }

  async function handleReinstate(userId: string) {
    const token = await getToken();
    await reinstate(token, userId);
    await load();
  }

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!profile) return <main className="p-8 text-gray-400">Loading…</main>;

  return (
    <main className="p-8 space-y-6 max-w-xl">
      <h1 className="text-xl font-semibold">User Detail</h1>

      <dl className="grid grid-cols-2 gap-2 text-sm">
        <dt className="text-gray-500">Name</dt><dd>{profile.display_name}</dd>
        <dt className="text-gray-500">Email</dt><dd>{profile.email}</dd>
        <dt className="text-gray-500">Role</dt><dd className="capitalize">{profile.role}</dd>
        <dt className="text-gray-500">Status</dt>
        <dd>
          <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
            profile.verification_status === "verified" ? "bg-green-100 text-green-700" :
            profile.verification_status === "suspended" ? "bg-red-100 text-red-700" :
            "bg-yellow-100 text-yellow-700"
          }`}>
            {profile.verification_status.replace(/_/g, " ")}
          </span>
        </dd>
        <dt className="text-gray-500">Submission lock</dt>
        <dd>{profile.is_submission_locked ? "Locked" : "Open"}</dd>
      </dl>

      <UserActionPanel
        userId={profile.id}
        currentStatus={profile.verification_status}
        onSuspend={handleSuspend}
        onReinstate={handleReinstate}
      />
    </main>
  );
}
