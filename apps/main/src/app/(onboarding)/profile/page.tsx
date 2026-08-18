"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { ProfilePhotoUpload } from "@/components/profile/ProfilePhotoUpload";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { updateMe, uploadPhoto } from "@/lib/api/profiles";
import { submitDocuments } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import type { Role } from "@fe-el-seka/shared";

const PHONE_RE = /^\+2\d{11}$/;

export default function ProfileOnboardingPage() {
  const router = useRouter();
  const t = useTranslations("onboarding.profile");
  const tDoc = useTranslations("onboarding.verifyDocuments");

  const [initializing, setInitializing] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [role, setRole] = useState<Role | null>(null);
  const [verificationStatus, setVerificationStatus] = useState<string | null>(null);
  const [lockout, setLockout] = useState<{ message: string; support_email?: string } | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [photoUploaded, setPhotoUploaded] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [frontId, setFrontId] = useState<File | null>(null);
  const [backId, setBackId] = useState<File | null>(null);
  const [license, setLicense] = useState<File | null>(null);

  useEffect(() => {
    async function init() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.replace("/login"); return; }

      const { data: profile } = await supabase
        .from("profiles")
        .select("role, display_name, phone_number, profile_photo_path, verification_status")
        .eq("id", session.user.id)
        .maybeSingle();

      if (!profile) { router.replace("/role-select"); return; }

      if (profile.verification_status === "verified") {
        router.replace("/");
        return;
      }

      if (profile.verification_status === "rejected") {
        router.replace(profile.role === "driver" ? "/driver/verify-documents" : "/verify-id");
        return;
      }

      setRole(profile.role as Role);
      setVerificationStatus(profile.verification_status);
      const savedName = profile.display_name === "New User" ? "" : (profile.display_name ?? "");
      setDisplayName(savedName);
      setPhoneNumber(profile.phone_number ?? "");
      setPhotoUploaded(!!profile.profile_photo_path);
      setInitializing(false);
    }
    init();
  }, [router]);

  const nameValid = displayName.trim().length >= 2;
  const phoneValid = PHONE_RE.test(phoneNumber.trim());

  const handlePhotoSelected = async (file: File) => {
    setPhotoError("");
    setPhotoUploading(true);
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }
    try {
      await uploadPhoto(session.access_token, file);
      setPhotoUploaded(true);
    } catch {
      setPhotoUploaded(false);
      setPhotoError(t("errors.photoUploadFailed"));
    } finally {
      setPhotoUploading(false);
    }
  };

  const handleNameBlur = async () => {
    if (!nameValid) return;
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    try {
      await updateMe(session.access_token, { display_name: displayName.trim() });
    } catch {
      // Best-effort incremental save — handleSubmit re-sends this as the source of truth.
    }
  };

  const handlePhoneBlur = async () => {
    if (!phoneValid) return;
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    try {
      await updateMe(session.access_token, { phone_number: phoneNumber.trim() });
    } catch {
      // Best-effort incremental save — handleSubmit re-sends this as the source of truth.
    }
  };

  const steps = [
    photoUploaded,
    nameValid,
    phoneValid,
    !!frontId,
    !!backId,
    ...(role === "driver" ? [!!license] : []),
  ];
  const completedSteps = steps.filter(Boolean).length;

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
    if (!photoUploaded) {
      setError(t("errors.photoRequired"));
      return;
    }
    if (!frontId || !backId) {
      setError(t("errors.idRequired"));
      return;
    }
    if (role === "driver" && !license) {
      setError(t("errors.licenseRequired"));
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
      });
      await submitDocuments(
        session.access_token,
        frontId,
        backId,
        role === "driver" ? (license ?? undefined) : undefined,
      );
      setVerificationStatus("pending_review");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string; support_email?: string };
      if (e?.error === "submission_locked") {
        setLockout({ message: e.message ?? "", support_email: e.support_email });
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

  if (lockout) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <div className="w-full max-w-sm">
          <LockoutMessage lockoutMessage={lockout.message} supportEmail={lockout.support_email} />
        </div>
      </main>
    );
  }

  if (verificationStatus === "pending_review") {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <div className="w-full max-w-sm text-center space-y-4">
          <h1 className="text-h3 text-content-primary">{t("documentsSubmittedTitle")}</h1>
          <p className="text-body-sm text-content-muted">
            {t("documentsSubmittedBody")}
          </p>
          <button
            onClick={() => router.push("/")}
            className="text-body-sm text-brand-primary underline"
          >
            {t("goToHome")}
          </button>
        </div>
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

        <div className="space-y-1">
          <div className="h-1.5 w-full bg-surface-bg rounded-full overflow-hidden">
            <div
              className="h-full bg-dash-primary rounded-full transition-all"
              style={{ width: `${(completedSteps / steps.length) * 100}%` }}
            />
          </div>
          <p className="text-caption text-content-muted text-end">
            {t("progressLabel", { completed: completedSteps, total: steps.length })}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="flex flex-col items-center gap-1">
            <ProfilePhotoUpload onFile={handlePhotoSelected} />
            {photoUploading && <p className="text-caption text-content-muted">{t("photoUploading")}</p>}
            {photoUploaded && !photoUploading && (
              <p className="text-caption text-status-completed">{t("photoUploadedLabel")}</p>
            )}
            {photoError && <p className="text-caption text-content-destructive">{photoError}</p>}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">
              {t("displayNameLabel")} {nameValid && <span className="text-status-completed">✓</span>}
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              onBlur={handleNameBlur}
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
              onBlur={handlePhoneBlur}
              placeholder={t("phonePlaceholder")}
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
              maxLength={16}
            />
          </div>

          <div className="border-t border-border-default pt-4 space-y-3">
            <p className="text-label text-content-secondary">{t("identityVerificationLabel")}</p>
            <p className="text-caption text-content-muted">{t("uploadNationalIdHint")}</p>
            <DocumentUpload label={tDoc("frontIdLabel")} onFile={setFrontId} required />
            <DocumentUpload label={tDoc("backIdLabel")} onFile={setBackId} required />
            {role === "driver" && (
              <DocumentUpload label={tDoc("licenseLabel")} onFile={setLicense} required />
            )}
          </div>

          {error && <p className="text-caption text-content-destructive">{error}</p>}

          <button
            type="submit"
            disabled={submitting || photoUploading}
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
