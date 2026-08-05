"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { setPassword, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

export default function SetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <SetPasswordForm />
    </Suspense>
  );
}

function SetPasswordForm() {
  const router = useRouter();
  const t = useTranslations("auth.setPassword");
  const isReset = useSearchParams().get("reason") === "reset";
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
      setError(t("errors.tooShort"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("errors.mismatch"));
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
        setError(sessionError.message ?? t("errors.signInFailed"));
        return;
      }
      window.location.replace("/profile");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? t("errors.setFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">
            {isReset ? t("titleReset") : t("titleSet")}
          </h1>
          <p className="text-body-sm text-content-muted mt-1">
            {isReset ? t("subtitleReset") : t("subtitleSet")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">{t("passwordLabel")}</label>
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
            <label className="text-label text-content-secondary">{t("confirmPasswordLabel")}</label>
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
            {loading ? t("saving") : isReset ? t("resetPassword") : t("setPassword")}
          </button>
          {!isReset && (
            <button
              type="button"
              onClick={() => router.push("/profile")}
              disabled={loading}
              className="w-full text-center text-body-sm text-content-muted hover:underline"
            >
              {t("skipForNow")}
            </button>
          )}
        </form>
      </div>
    </main>
  );
}
