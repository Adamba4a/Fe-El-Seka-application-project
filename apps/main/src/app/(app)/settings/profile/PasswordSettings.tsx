"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { setPassword, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";

export function PasswordSettings({ accessToken }: { accessToken: string }) {
  const t = useTranslations("settings.profile.password");
  const tc = useTranslations("common");
  const [expanded, setExpanded] = useState(false);
  const [password, setPasswordValue] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (password.length < 8) {
      setError(t("tooShort"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("mismatch"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setPassword(accessToken, password);
      // Supabase revokes the current session as soon as the password
      // changes, so the accessToken above is now dead — sign back in with
      // the new password to refresh the cookies before the user navigates
      // away, or they'd get silently bounced to /login on the next request.
      const supabase = createClient();
      const { data: { session: currentSession } } = await supabase.auth.getSession();
      if (currentSession?.user.email) {
        const newSession = await signInWithPassword(currentSession.user.email, password);
        await supabase.auth.setSession({
          access_token: newSession.access_token,
          refresh_token: newSession.refresh_token,
        });
      }
      setPasswordValue("");
      setConfirmPassword("");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? t("genericError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-dash-surface rounded-2xl shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between p-5"
      >
        <span className="flex items-center gap-2 font-bold text-dash-navy">
          <span aria-hidden="true">🔒</span>
          {t("heading")}
        </span>
        <span className={`text-dash-text-muted transition-transform ${expanded ? "rotate-180" : ""}`}>▾</span>
      </button>
      {expanded && (
        <div className="px-5 pb-5 space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-caption text-dash-text-muted">{t("newPasswordLabel")}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPasswordValue(e.target.value)}
              disabled={saving}
              className="bg-dash-bg border border-transparent rounded-xl px-3 py-2 text-body-sm text-dash-navy outline-none focus:border-dash-primary transition-colors"
              autoComplete="new-password"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-caption text-dash-text-muted">{t("confirmPasswordLabel")}</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={saving}
              className="bg-dash-bg border border-transparent rounded-xl px-3 py-2 text-body-sm text-dash-navy outline-none focus:border-dash-primary transition-colors"
              autoComplete="new-password"
            />
          </div>
          {error && <p className="text-caption text-content-destructive">{error}</p>}
          {saved && <p className="text-caption text-status-completed">{t("saved")}</p>}
          <button
            onClick={handleSave}
            disabled={saving || !password || !confirmPassword}
            className="w-full bg-dash-primary hover:opacity-90 text-white rounded-xl py-2 text-body-sm font-semibold disabled:opacity-50 transition-opacity"
          >
            {saving ? tc("saving") : t("updatePassword")}
          </button>
        </div>
      )}
    </div>
  );
}
