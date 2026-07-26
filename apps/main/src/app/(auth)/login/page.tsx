"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { requestOtp, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

function GoogleIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden>
      <path fill="#4285F4" d="M23.766 12.276c0-.818-.074-1.606-.21-2.361H12.24v4.467h6.482a5.54 5.54 0 01-2.402 3.632v3.017h3.885c2.276-2.098 3.561-5.185 3.561-8.755z" />
      <path fill="#34A853" d="M12.24 24c3.24 0 5.956-1.075 7.942-2.906l-3.885-3.017c-1.078.724-2.46 1.15-4.057 1.15-3.12 0-5.763-2.107-6.706-4.938H1.518v3.11A11.997 11.997 0 0012.24 24z" />
      <path fill="#FBBC05" d="M5.534 14.29a7.196 7.196 0 010-4.58V6.6H1.518a12.003 12.003 0 000 10.8l4.016-3.11z" />
      <path fill="#EA4335" d="M12.24 4.771c1.762 0 3.344.606 4.589 1.795l3.442-3.442C18.192 1.19 15.476 0 12.24 0 7.68 0 3.73 2.612 1.518 6.6l4.016 3.11c.943-2.831 3.586-4.938 6.706-4.938z" />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M17.94 17.94A10.94 10.94 0 0112 20c-7 0-11-8-11-8a21.86 21.86 0 015.06-6.06M9.9 4.24A10.94 10.94 0 0112 4c7 0 11 8 11 8a21.8 21.8 0 01-3.22 4.44M14.12 14.12a3 3 0 11-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function KeyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777Zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  );
}

function LockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"password" | "code">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSent, setResetSent] = useState(false);

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

  const handleForgotPassword = async () => {
    if (!isValidEmail) {
      setError("Enter your email address above first");
      return;
    }
    setResetLoading(true);
    setError("");
    try {
      const supabase = createClient();
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent("/set-password?reason=reset")}`,
      });
      if (resetError) {
        setError(resetError.message ?? "Could not send reset email. Please try again.");
      } else {
        setResetSent(true);
      }
    } catch {
      setError("Could not send reset email. Please try again.");
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-[#F3EAD8]">
      <div className="w-full max-w-sm">
        <div className="bg-surface-card rounded-3xl shadow-lg p-8 space-y-6">
          <div className="text-center space-y-1">
            <h1 className="text-2xl font-bold text-brand-primary">Welcome to Triplyy</h1>
            <p className="text-body-sm text-content-muted">
              {mode === "password"
                ? "Sign in to start sharing your journey."
                : "Enter your email to receive a verification code"}
            </p>
          </div>

          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-border-default rounded-xl font-medium text-content-primary hover:bg-surface-bg disabled:opacity-50 transition-colors"
          >
            {googleLoading ? <Spinner /> : <GoogleIcon />}
            {googleLoading ? "Redirecting…" : "Continue with Google"}
          </button>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border-default" />
            <span className="text-caption text-content-muted uppercase tracking-wide">or</span>
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
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setResetSent(false);
                  }}
                  disabled={loading}
                  className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
                  autoComplete="email"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-label text-content-secondary">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    className="w-full px-3 py-2 pr-10 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus disabled:bg-surface-bg transition-colors"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-content-muted"
                  >
                    {showPassword ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                  </button>
                </div>
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

              <div className="text-center">
                {resetSent ? (
                  <p className="text-body-sm text-content-muted">
                    Check <strong className="text-content-secondary">{email}</strong> for a reset link
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={handleForgotPassword}
                    disabled={resetLoading}
                    className="text-body-sm text-brand-primary hover:underline disabled:opacity-50"
                  >
                    {resetLoading ? "Sending…" : "Forgot password?"}
                  </button>
                )}
              </div>

              <div className="h-px bg-border-default" />

              <p className="text-center text-body-sm text-content-muted">
                New here?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("code");
                    setError("");
                  }}
                  className="text-brand-primary hover:underline font-medium"
                >
                  Create an account
                </button>
              </p>

              <p className="text-center text-body-sm">
                <button
                  type="button"
                  onClick={() => {
                    setMode("code");
                    setError("");
                  }}
                  className="inline-flex items-center gap-1.5 text-brand-primary hover:underline"
                >
                  <KeyIcon className="w-4 h-4" />
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

        <p className="mt-4 flex items-center justify-center gap-1.5 text-caption text-content-muted">
          <LockIcon className="w-3.5 h-3.5" />
          Secure encryption active
        </p>
      </div>
    </main>
  );
}
