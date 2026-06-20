"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { ProfilePhotoUpload } from "@/components/profile/ProfilePhotoUpload";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { updateMe, uploadPhoto } from "@/lib/api/profiles";
import { submitDocuments } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import type { Role } from "@fe-el-seka/shared";

export default function ProfileOnboardingPage() {
  const router = useRouter();

  const [initializing, setInitializing] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [role, setRole] = useState<Role | null>(null);
  const [verificationStatus, setVerificationStatus] = useState<string | null>(null);
  const [lockout, setLockout] = useState<{ message: string; support_email?: string } | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
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
        .select("role, display_name, verification_status")
        .eq("id", session.user.id)
        .maybeSingle();

      if (!profile) { router.replace("/role-select"); return; }

      if (profile.verification_status === "verified") {
        router.replace("/");
        return;
      }

      setRole(profile.role as Role);
      setVerificationStatus(profile.verification_status);
      const savedName = profile.display_name === "New User" ? "" : (profile.display_name ?? "");
      setDisplayName(savedName);
      setInitializing(false);
    }
    init();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim() || displayName.trim().length < 2) {
      setError("Please enter your name (min 2 characters)");
      return;
    }
    if (!frontId || !backId) {
      setError("Please upload both sides of your National ID");
      return;
    }
    if (role === "driver" && !license) {
      setError("Please upload your Driving License");
      return;
    }

    setSubmitting(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      await updateMe(session.access_token, { display_name: displayName.trim() });
      if (photo) await uploadPhoto(session.access_token, photo);
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
        setError(e?.message ?? "Submission failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (initializing) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <p className="text-body-sm text-content-muted">Loading…</p>
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
          <h1 className="text-h3 text-content-primary">Documents submitted</h1>
          <p className="text-body-sm text-content-muted">
            Your identity is under review. We will notify you once a decision is made.
          </p>
          <button
            onClick={() => router.push("/")}
            className="text-body-sm text-brand-primary underline"
          >
            Go to home
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6 py-8">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">Complete your profile</h1>
          <p className="text-body-sm text-content-muted mt-1">
            {verificationStatus === "rejected"
              ? "Your documents were rejected. Please resubmit."
              : "Set up your account to get started"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <ProfilePhotoUpload onFile={setPhoto} />

          <div className="flex flex-col gap-1">
            <label className="text-label text-content-secondary">Display name *</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
              className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
              maxLength={50}
            />
          </div>

          <div className="border-t border-border-default pt-4 space-y-3">
            <p className="text-label text-content-secondary">Identity verification</p>
            <p className="text-caption text-content-muted">Upload your Egyptian National ID card</p>
            <DocumentUpload label="National ID — Front" onFile={setFrontId} required />
            <DocumentUpload label="National ID — Back" onFile={setBackId} required />
            {role === "driver" && (
              <DocumentUpload label="Driving License" onFile={setLicense} required />
            )}
          </div>

          {error && <p className="text-caption text-content-destructive">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {submitting && <Spinner />}
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </form>
      </div>
    </main>
  );
}
