"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { VerificationStatusBadge } from "@/components/verification/VerificationStatus";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { submitDocuments } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";
import type { VerificationStatus } from "@fe-el-seka/shared";

export default function VerifyIdPage() {
  const router = useRouter();
  const [frontId, setFrontId] = useState<File | null>(null);
  const [backId, setBackId] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState<VerificationStatus | null>(null);
  const [lockout, setLockout] = useState<{ message: string; support_email?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frontId || !backId) { setError("Please upload both ID photos"); return; }
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      const result = await submitDocuments(session.access_token, frontId, backId);
      setSubmitted({ verification_status: result.status, attempt_number: result.attempt_number, is_locked: false, rejection_reason: null, lockout_message: null });
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string; support_email?: string; lockout_message?: string };
      if (e?.error === "submission_locked") {
        setLockout({ message: e.message ?? "", support_email: e.support_email });
      } else {
        setError(e?.message ?? "Submission failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (lockout) return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <LockoutMessage lockoutMessage={lockout.message} supportEmail={lockout.support_email} />
      </div>
    </main>
  );

  if (submitted) return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-xl font-bold">Documents submitted</h1>
        <VerificationStatusBadge status={submitted} />
        <p className="text-sm text-gray-500">We will notify you once your identity has been reviewed.</p>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-xl font-bold">Verify your identity</h1>
          <p className="text-gray-500 text-sm mt-1">Upload your Egyptian National ID card</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <DocumentUpload label="National ID — Front" onFile={setFrontId} required />
          <DocumentUpload label="National ID — Back" onFile={setBackId} required />
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={loading || !frontId || !backId}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
          >
            {loading ? "Submitting…" : "Submit for Review"}
          </button>
        </form>
      </div>
    </main>
  );
}
