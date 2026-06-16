"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createBrowserClient } from "@supabase/ssr";
import type { AdminSubmissionDetail } from "@fe-el-seka/shared";
import { getSubmission, approve, reject, unlock } from "@/lib/api/admin-verification";
import { DocumentViewer } from "@/components/verification/DocumentViewer";
import { ApproveButton } from "@/components/verification/ApproveButton";
import { RejectForm } from "@/components/verification/RejectForm";
import { UnlockButton } from "@/components/verification/UnlockButton";

const sb = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export default function SubmissionDetailPage({ params }: { params: { submission_id: string } }) {
  const router = useRouter();
  const [detail, setDetail] = useState<AdminSubmissionDetail | null>(null);
  const [error, setError] = useState("");

  async function getToken(): Promise<string> {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        setDetail(await getSubmission(token, params.submission_id));
      } catch {
        setError("Failed to load submission");
      }
    })();
  }, [params.submission_id]);

  async function handleApprove() {
    const token = await getToken();
    await approve(token, params.submission_id);
    router.push("/verification");
  }

  async function handleReject(reason: string) {
    const token = await getToken();
    await reject(token, params.submission_id, reason);
    router.push("/verification");
  }

  async function handleUnlock(userId: string) {
    const token = await getToken();
    await unlock(token, userId);
    router.refresh();
  }

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!detail) return <main className="p-8 text-gray-400">Loading…</main>;

  const { front_id, back_id, license } = detail.document_signed_urls;
  const docUrls = [front_id, back_id, ...(license ? [license] : [])];
  const labels =
    detail.submission_type === "driver_id_license" && license
      ? ["Front ID", "Back ID", "License"]
      : ["Front ID", "Back ID"];

  return (
    <main className="p-8 space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold">Submission Detail</h1>

      <dl className="grid grid-cols-2 gap-2 text-sm">
        <dt className="text-gray-500">User</dt><dd>{detail.user_name}</dd>
        <dt className="text-gray-500">Email</dt><dd>{detail.email}</dd>
        <dt className="text-gray-500">Type</dt><dd className="capitalize">{detail.submission_type.replace(/_/g, " ")}</dd>
        <dt className="text-gray-500">Submitted</dt><dd>{new Date(detail.submitted_at).toLocaleString()}</dd>
        <dt className="text-gray-500">Attempt</dt><dd>{detail.attempt_number}/3</dd>
      </dl>

      <DocumentViewer signedUrls={docUrls} labels={labels} />

      <div className="flex flex-wrap gap-3 pt-2">
        <ApproveButton onApprove={handleApprove} />
        <RejectForm attemptNumber={detail.attempt_number} onReject={handleReject} />
        {detail.attempt_number >= 3 && (
          <UnlockButton userId={detail.user_id} onUnlock={handleUnlock} />
        )}
      </div>
    </main>
  );
}
