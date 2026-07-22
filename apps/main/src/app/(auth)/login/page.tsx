"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { requestOtp, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"password" | "code">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const isValidEmail = email.includes("@") && email.includes(".");

  const handleCodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail) {
      setError("Enter a valid email address");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await requestOtp(email);
      sessionStorage.setItem("otp_email", email);
      router.push("/otp");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "otp_rate_limited") {
        setError("Too many requests. Please wait 15 minutes before trying again.");
      } else {
        setError(e?.message ?? "Failed to send code. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail) {
      setError("Enter a valid email address");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const session = await signInWithPassword(email, password);

      const supabase = createClient();
      const { error: sessionError } = await supabase.auth.setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      });

      if (sessionError) {
        setError(sessionError.message ?? "Could not establish session. Please try again.");
        return;
      }

      window.location.replace(session.user.is_new_user ? "/role-select" : "/");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "invalid_credentials") {
        setError("Incorrect email or password.");
      } else {
        setError(e?.message ?? "Failed to sign in. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError("");
    try {
      const supabase = createClient();
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${window.location.origin}/auth/callback` },
      });
      if (oauthError) {
        setError(oauthError.message ?? "Could not start Google sign-in.");
        setGoogleLoading(false);
      }
    } catch {
      setError("Could not start Google sign-in.");
      setGoogleLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">Sign in to Triplyy</h1>
          <p className="text-body-sm text-content-muted mt-1">
            {mode === "password"
              ? "Enter your email and password to sign in"
              : "Enter your email to receive a verification code"}
          </p>
        </div>

        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={googleLoading}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-border-default rounded-xl font-medium text-content-primary hover:bg-surface-bg disabled:opacity-50 transition-colors"
        >
          {googleLoading && <Spinner />}
          {googleLoading ? "Redirecting…" : "Continue with Google"}
        </button>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-border-default" />
          <span className="text-caption text-content-muted">or</span>
          <div className="h-px flex-1 bg-border-default" />
        </div>

        {mode === "password" ? (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div className="flex flex-col gap-1">
              <label className="text-label text-content-secondary">Email address</label>
              <input
                type="email"
                inputMode="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
                autoComplete="email"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-label text-content-secondary">Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
                autoComplete="current-password"
              />
              {error && <p className="text-caption text-content-destructive">{error}</p>}
            </div>
            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
            >
              {loading && <Spinner />}
              {loading ? "Signing in…" : "Sign In"}
            </button>
            <p className="text-center text-body-sm text-content-muted">
              New here, or forgot your password?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("code");
                  setError("");
                }}
                className="text-brand-primary hover:underline"
              >
                Sign in with a code instead
              </button>
            </p>
          </form>
        ) : (
          <form onSubmit={handleCodeSubmit} className="space-y-4">
            <div className="flex flex-col gap-1">
              <label className="text-label text-content-secondary">Email address</label>
              <input
                type="email"
                inputMode="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
                autoComplete="email"
              />
              {error && <p className="text-caption text-content-destructive">{error}</p>}
            </div>
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
            >
              {loading && <Spinner />}
              {loading ? "Sending…" : "Send Code"}
            </button>
            <p className="text-center text-body-sm text-content-muted">
              Already set a password?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("password");
                  setError("");
                }}
                className="text-brand-primary hover:underline"
              >
                Sign in with password
              </button>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}
