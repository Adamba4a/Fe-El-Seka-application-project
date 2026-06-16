import { createAdminClient } from "@/lib/supabase/admin-client";
import { SubmissionQueue } from "@/components/verification/SubmissionQueue";
import type { AdminQueueItem } from "@fe-el-seka/shared";
import Link from "next/link";

interface SearchParams { type?: string; page?: string }

export default async function VerificationQueuePage({ searchParams }: { searchParams: SearchParams }) {
  const supabase = createAdminClient();

  const type = searchParams.type;
  const page = Number(searchParams.page ?? 1);
  const limit = 20;
  const offset = (page - 1) * limit;

  let query = supabase
    .from("verification_submissions")
    .select("id, user_id, submission_type, submitted_at, attempt_number, profiles(display_name, email)")
    .eq("status", "pending_review")
    .order("submitted_at", { ascending: true })
    .range(offset, offset + limit - 1);

  if (type) query = query.eq("submission_type", type);

  const { data } = await query;

  const items: AdminQueueItem[] = (data ?? []).map((row: any) => ({
    submission_id: row.id,
    user_id: row.user_id,
    user_name: row.profiles?.display_name ?? "",
    email: row.profiles?.email ?? "",
    submission_type: row.submission_type,
    submitted_at: row.submitted_at,
    attempt_number: row.attempt_number,
  }));

  const tabs = ["all", "passenger_id", "driver_id", "vehicle"];

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Verification Queue</h1>
        <Link href="/verification/history" className="text-sm text-blue-600 hover:underline">
          View history
        </Link>
      </div>

      <div className="flex gap-2">
        {tabs.map((t) => (
          <Link
            key={t}
            href={t === "all" ? "/verification" : `/verification?type=${t}`}
            className={`px-3 py-1.5 rounded text-sm border capitalize ${(!type && t === "all") || type === t ? "bg-gray-900 text-white border-gray-900" : "bg-white hover:bg-gray-50"}`}
          >
            {t.replace(/_/g, " ")}
          </Link>
        ))}
      </div>

      <SubmissionQueue items={items} />

      <div className="flex gap-4 text-sm">
        {page > 1 && <Link href={`?${type ? `type=${type}&` : ""}page=${page - 1}`} className="text-blue-600 hover:underline">Previous</Link>}
        {items.length === limit && <Link href={`?${type ? `type=${type}&` : ""}page=${page + 1}`} className="text-blue-600 hover:underline">Next</Link>}
      </div>
    </main>
  );
}
