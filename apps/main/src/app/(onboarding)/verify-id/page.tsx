"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { submitDocuments, getStatus } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";

export default function VerifyIdPage() {
  const router = useRouter();
  const [initializing, setInitializing] = useState(true);
  const [frontId, setFrontId] = useState<File | null>(null);
  const [backId, setBackId] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [lockout, setLockout] = useState<{ message: string; support_email?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
      } catch {
        // no prior submission — show form
      }
      setInitializing(false);
    }
    checkStatus();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frontId || !backId) { setError("Please upload both ID photos"); return; }
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      await submitDocuments(session.access_token, frontId, backId);
      setSubmitted(true);
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string; support_email?: string };
      if (e?.error === "submission_locked") {
        setLockout({ message: e.message ?? "", support_email: e.support_email });
      } else {
        setError(e?.message ?? "Submission failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (initializing) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <p className="text-body-sm text-content-muted">Loading…</p>
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
        <h1 className="text-h3 text-content-primary">Documents submitted</h1>
        <p className="text-body-sm text-content-muted">We will notify you once your identity has been reviewed.</p>
        <button onClick={() => router.push("/")} className="text-body-sm text-brand-primary underline">
          Go to home
        </button>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h3 text-content-primary">Verify your identity</h1>
          <p className="text-body-sm text-content-muted mt-1">Upload your Egyptian National ID card</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <DocumentUpload label="National ID — Front" onFile={setFrontId} required />
          <DocumentUpload label="National ID — Back" onFile={setBackId} required />
          {error && <p className="text-caption text-content-destructive">{error}</p>}
          <button
            type="submit"
            disabled={loading || !frontId || !backId}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {loading && <Spinner />}
            {loading ? "Submitting…" : "Submit for Review"}
          </button>
        </form>
      </div>
    </main>
  );
}
