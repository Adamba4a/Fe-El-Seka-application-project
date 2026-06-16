"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { LockoutMessage } from "@/components/verification/LockoutMessage";
import { submitDocuments, getStatus } from "@/lib/api/verification";
import { createClient } from "@/lib/supabase/client";

export default function DriverVerifyDocumentsPage() {
  const router = useRouter();
  const [initializing, setInitializing] = useState(true);
  const [frontId, setFrontId] = useState<File | null>(null);
  const [backId, setBackId] = useState<File | null>(null);
  const [license, setLicense] = useState<File | null>(null);
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
    if (!frontId || !backId || !license) { setError("Please upload all three documents"); return; }
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    try {
      await submitDocuments(session.access_token, frontId, backId, license);
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
      <main className="min-h-screen flex items-center justify-center p-4">
        <p className="text-gray-400">Loading…</p>
      </main>
    );
  }

  if (lockout) return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <LockoutMessage lockoutMessage={lockout.message} supportEmail={lockout.support_email} />
      </div>
    </main>
  );

  if (submitted) return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm text-center space-y-4">
        <h1 className="text-xl font-bold">Documents submitted</h1>
        <p className="text-sm text-gray-500">We will review your documents. Once approved you can register your vehicle.</p>
        <button onClick={() => router.push("/")} className="text-blue-600 text-sm underline">
          Go to home
        </button>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-xl font-bold">Driver Verification</h1>
          <p className="text-gray-500 text-sm mt-1">Upload your National ID and Driving License</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <DocumentUpload label="National ID — Front" onFile={setFrontId} required />
          <DocumentUpload label="National ID — Back" onFile={setBackId} required />
          <DocumentUpload label="Driving License" onFile={setLicense} required />
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={loading || !frontId || !backId || !license}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
          >
            {loading ? "Submitting…" : "Submit for Review"}
          </button>
        </form>
      </div>
    </main>
  );
}
