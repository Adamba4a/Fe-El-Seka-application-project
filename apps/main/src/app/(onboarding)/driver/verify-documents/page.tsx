"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { submitDocuments, getStatus } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

export default function DriverVerifyDocumentsPage() {
  const router = useRouter();
  const t = useTranslations("onboarding.verifyDocuments");
  const tStatus = useTranslations("onboarding.verificationStatus");
  const [initializing, setInitializing] = useState(true);
  const [frontId, setFrontId] = useState<File | null>(null);
  const [backId, setBackId] = useState<File | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);
  const [license, setLicense] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [lockout, setLockout] = useState<{ message: string; support_email?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rejectionReason, setRejectionReason] = useState<string | null>(null);

  useEffect(() => {
    async function checkStatus() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.replace("/login"); return; }
      try {
        const status = await getStatus(session.access_token);
        if (status.verification_status === "verified") {
          router.replace("/");
          return;
        }
        if (status.verification_status === "pending_review") {
          setSubmitted(true);
        }
        if (status.verification_status === "rejected" && status.rejection_reason) {
          setRejectionReason(status.rejection_reason);
        }
      } catch {
        // no prior submission — show form
      }
      setInitializing(false);
    }
    checkStatus();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frontId || !backId || !selfie || !license) { setError(t("errors.allRequired")); return; }
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      await submitDocuments(session.access_token, frontId, backId, selfie, license);
      setSubmitted(true);
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string; support_email?: string };
      if (e?.error === "submission_locked") {
        setLockout({ message: e.message ?? "", support_email: e.support_email });
      } else {
        setError(e?.message ?? t("errors.submissionFailed"));
      }
    } finally {
      setLoading(false);
    }
  };

  if (initializing) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <p className="text-body-sm text-content-muted">{t("loading")}</p>
      </main>
    );
  }

  if (lockout) return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm">
        <LockoutMessage lockoutMessage={lockout.message} supportEmail={lockout.support_email} />
      </div>
    </main>
  );

  if (submitted) return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm text-center space-y-4">
        <h1 className="text-h3 text-content-primary">{t("documentsSubmittedTitle")}</h1>
        <p className="text-body-sm text-content-muted">{t("documentsSubmittedBody")}</p>
        <button onClick={() => router.push("/")} className="text-body-sm text-brand-primary underline">
          {t("goToHome")}
        </button>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <a href="/" className="inline-block text-content-primary hover:opacity-70 text-lg leading-none">
          <span className="inline-block rtl:rotate-180">←</span>
        </a>
        <div className="text-center">
          <h1 className="text-h3 text-content-primary">{t("title")}</h1>
          <p className="text-body-sm text-content-muted mt-1">{t("subtitle")}</p>
        </div>

        {rejectionReason && (
          <div className="bg-status-cancelled-bg border border-status-cancelled rounded-xl px-4 py-3 text-start">
            <p className="text-caption text-content-destructive uppercase tracking-wide mb-1">
              {tStatus("reasonLabel")}
            </p>
            <p className="text-body-sm text-content-secondary">{rejectionReason}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <DocumentUpload label={t("frontIdLabel")} onFile={setFrontId} required />
          <DocumentUpload label={t("backIdLabel")} onFile={setBackId} required />
          <DocumentUpload label={t("selfieLabel")} onFile={setSelfie} required capture="user" />
          <DocumentUpload label={t("licenseLabel")} onFile={setLicense} required />
          {error && <p className="text-caption text-content-destructive">{error}</p>}
          <button
            type="submit"
            disabled={loading || !frontId || !backId || !selfie || !license}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-opacity"
          >
            {loading && <Spinner />}
            {loading ? t("submitting") : t("submitForReview")}
          </button>
        </form>
      </div>
    </main>
  );
}
