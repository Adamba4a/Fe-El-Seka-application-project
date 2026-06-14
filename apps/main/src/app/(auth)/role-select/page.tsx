"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RoleSelector } from "@/components/auth/RoleSelector";
import { setupProfile } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";

export default function RoleSelectPage() {
  const router = useRouter();
  const [role, setRole] = useState<"passenger" | "driver" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleContinue = async () => {
    if (!role) return;
    setLoading(true);
    setError("");
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.replace("/login"); return; }
      try {
        await setupProfile(session.access_token, { role, display_name: "New User" });
      } catch (err: unknown) {
        const e = err as { detail?: { error?: string; message?: string } | string; message?: string };
        const detail = typeof e?.detail === "object" ? e.detail : null;
        if (detail?.error === "already_exists") {
          // Profile already created on a prior attempt — skip forward.
          router.push("/profile");
          return;
        }
        const msg = detail?.message ?? (e as { message?: string })?.message;
        setError(msg ?? "Could not save role. Please try again.");
        return;
      }
      router.push("/profile");
    } catch (err: unknown) {
      setError("Unexpected error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">How will you use Fe El Seka?</h1>
          <p className="text-gray-500 text-sm mt-1">This cannot be changed later</p>
        </div>

        <RoleSelector value={role} onChange={setRole} />

        {error && <p className="text-red-500 text-xs text-center">{error}</p>}

        <button
          onClick={handleContinue}
          disabled={!role || loading}
          className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
        >
          {loading ? "Saving…" : "Continue"}
        </button>
      </div>
    </main>
  );
}
