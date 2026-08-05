"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { setPassword, signInWithPassword } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";

export function PasswordSettings({ accessToken }: { accessToken: string }) {
  const t = useTranslations("settings.profile.password");
  const tc = useTranslations("common");
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
    <div className="space-y-3">
      <h2 className="font-semibold text-content-primary">{t("heading")}</h2>
      <div className="bg-surface-bg rounded-xl p-4 space-y-3">
        <div className="flex flex-col gap-1">
          <label className="text-caption text-content-muted">{t("newPasswordLabel")}</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPasswordValue(e.target.value)}
            disabled={saving}
            className="border border-border-default rounded-md px-2 py-1.5 text-body-sm outline-none focus:border-border-focus transition-colors"
            autoComplete="new-password"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-caption text-content-muted">{t("confirmPasswordLabel")}</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={saving}
            className="border border-border-default rounded-md px-2 py-1.5 text-body-sm outline-none focus:border-border-focus transition-colors"
            autoComplete="new-password"
          />
        </div>
        {error && <p className="text-caption text-content-destructive">{error}</p>}
        {saved && <p className="text-caption text-status-completed">{t("saved")}</p>}
        <button
          onClick={handleSave}
          disabled={saving || !password || !confirmPassword}
          className="w-full bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-2 text-body-sm font-medium disabled:opacity-50 transition-colors"
        >
          {saving ? tc("saving") : t("updatePassword")}
        </button>
      </div>
    </div>
  );
}
