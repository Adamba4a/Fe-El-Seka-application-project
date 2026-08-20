"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { updateMe } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import type { Role } from "@fe-el-seka/shared";

const PHONE_RE = /^\+2\d{11}$/;

export default function ProfileOnboardingPage() {
  const router = useRouter();
  const t = useTranslations("onboarding.profile");

  const [initializing, setInitializing] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [role, setRole] = useState<Role | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");

  useEffect(() => {
    async function init() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.replace("/login"); return; }

      const { data: profile } = await supabase
        .from("profiles")
        .select("role, display_name, phone_number, date_of_birth, verification_status")
        .eq("id", session.user.id)
        .maybeSingle();

      if (!profile) { router.replace("/role-select"); return; }

      if (profile.verification_status === "rejected") {
        router.replace(profile.role === "driver" ? "/driver/verify-documents" : "/verify-id");
        return;
      }

      setRole(profile.role as Role);
      const savedName = profile.display_name === "New User" ? "" : (profile.display_name ?? "");
      setDisplayName(savedName);
      setPhoneNumber(profile.phone_number ?? "");
      setDateOfBirth(profile.date_of_birth ?? "");
      setInitializing(false);
    }
    init();
  }, [router]);

  const nameValid = displayName.trim().length >= 2;
  const phoneValid = PHONE_RE.test(phoneNumber.trim());
  const dobValid = dateOfBirth.trim().length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim() || displayName.trim().length < 2) {
      setError(t("errors.nameTooShort"));
      return;
    }
    if (!PHONE_RE.test(phoneNumber.trim())) {
      setError(t("errors.phoneInvalid"));
      return;
    }
    if (!dateOfBirth.trim()) {
      setError(t("errors.dobRequired"));
      return;
    }

    setSubmitting(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      await updateMe(session.access_token, {
        display_name: displayName.trim(),
        phone_number: phoneNumber.trim(),
        date_of_birth: dateOfBirth,
      });
      router.push(role === "driver" ? "/" : "/dashboard");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "underage") {
        setError(t("errors.underage"));
      } else {
        setError(e?.message ?? t("errors.submissionFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (initializing) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <p className="text-body-sm text-content-muted">{t("loading")}</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6 py-8">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">{t("title")}</h1>
          <p className="text-body-sm text-content-muted mt-1">{t("subtitleDefault")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">
              {t("displayNameLabel")} {nameValid && <span className="text-status-completed">✓</span>}
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("displayNamePlaceholder")}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
              maxLength={50}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">
              {t("phoneLabel")} {phoneValid && <span className="text-status-completed">✓</span>}
            </label>
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder={t("phonePlaceholder")}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
              maxLength={16}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">
              {t("dateOfBirthLabel")} {dobValid && <span className="text-status-completed">✓</span>}
            </label>
            <input
              type="date"
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
            />
          </div>

          {error && <p className="text-caption text-content-destructive">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-opacity"
          >
            {submitting && <Spinner />}
            {submitting ? t("submitting") : t("submit")}
          </button>
        </form>
      </div>
    </main>
  );
}
