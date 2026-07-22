"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setPassword, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

export default function SetPasswordPage() {
  const router = useRouter();
  const [accessToken, setAccessToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPasswordValue] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setAccessToken(session.access_token);
      setEmail(session.user.email ?? "");
    });
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await setPassword(accessToken, password);
      // Supabase revokes the current session's access/refresh tokens as soon
      // as the password changes, even though the request that changed it used
      // that same token — the old cookies are dead now, so we must sign back
      // in with the new password to get a fresh, valid session before
      // navigating (a plain client-side push would hit middleware with a
      // revoked session and bounce back to /login).
      const session = await signInWithPassword(email, password);
      const supabase = createClient();
      const { error: sessionError } = await supabase.auth.setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      });
      if (sessionError) {
        setError(sessionError.message ?? "Password set, but could not sign you back in. Please sign in again.");
        return;
      }
      window.location.replace("/profile");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Could not set password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">Set a password</h1>
          <p className="text-body-sm text-content-muted mt-1">
            Skip the code next time by setting a password now
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">Password</label>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPasswordValue(e.target.value)}
              disabled={loading}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
              autoComplete="new-password"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">Confirm password</label>
            <input
              type="password"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
              autoComplete="new-password"
            />
            {error && <p className="text-caption text-content-destructive">{error}</p>}
          </div>
          <button
            type="submit"
            disabled={loading || !password || !confirmPassword}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {loading && <Spinner />}
            {loading ? "Saving…" : "Set Password"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/profile")}
            disabled={loading}
            className="w-full text-center text-body-sm text-content-muted hover:underline"
          >
            Skip for now
          </button>
        </form>
      </div>
    </main>
  );
}
