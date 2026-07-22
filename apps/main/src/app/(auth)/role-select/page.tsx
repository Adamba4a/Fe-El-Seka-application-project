"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RoleSelector } from "@/components/auth/RoleSelector";
import { setupProfile } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

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
          router.push("/profile");
          return;
        }
        const msg = detail?.message ?? (e as { message?: string })?.message;
        setError(msg ?? "Could not save role. Please try again.");
        return;
      }
      // Google users already have provider-managed auth — a local password
      // is optional (available later from Settings), not part of onboarding.
      router.push(session.user.app_metadata?.provider === "google" ? "/profile" : "/set-password");
    } catch {
      setError("Unexpected error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">How will you use Triplyy?</h1>
          <p className="text-body-sm text-content-muted mt-1">This cannot be changed later</p>
        </div>

        <RoleSelector value={role} onChange={setRole} />

        {error && <p className="text-caption text-content-destructive text-center">{error}</p>}

        <button
          onClick={handleContinue}
          disabled={!role || loading}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
        >
          {loading && <Spinner />}
          {loading ? "Saving…" : "Continue"}
        </button>
      </div>
    </main>
  );
}
