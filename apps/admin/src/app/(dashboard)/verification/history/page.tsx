import { createAdminClient } from "@/lib/supabase/admin-client";
import Link from "next/link";

interface SearchParams { page?: string }

export default async function VerificationHistoryPage({ searchParams }: { searchParams: SearchParams }) {
  const page = Number(searchParams.page ?? 1);
  const limit = 20;
  const offset = (page - 1) * limit;

  const supabase = createAdminClient();

  const { data } = await supabase
    .from("verification_submissions")
    .select("id, status, reviewed_at, reviewer_id, profiles(display_name)")
    .neq("status", "pending_review")
    .order("reviewed_at", { ascending: false })
    .range(offset, offset + limit - 1);

  const rows = data ?? [];

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/verification" className="text-sm text-blue-600 hover:underline">← Queue</Link>
        <h1 className="text-2xl font-semibold">Review History</h1>
      </div>

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-2 pr-4 font-medium">User</th>
            <th className="pb-2 pr-4 font-medium">Outcome</th>
            <th className="pb-2 font-medium">Reviewed At</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any) => (
            <tr key={row.id} className="border-b">
              <td className="py-3 pr-4">{(row.profiles as any)?.display_name ?? "—"}</td>
              <td className="py-3 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${row.status === "approved" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {row.status}
                </span>
              </td>
              <td className="py-3 text-gray-500">{row.reviewed_at ? new Date(row.reviewed_at).toLocaleString() : "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={3} className="py-8 text-center text-gray-400">No history yet</td></tr>
          )}
        </tbody>
      </table>

      <div className="flex gap-4 text-sm">
        {page > 1 && <Link href={`?page=${page - 1}`} className="text-blue-600 hover:underline">Previous</Link>}
        {rows.length === limit && <Link href={`?page=${page + 1}`} className="text-blue-600 hover:underline">Next</Link>}
      </div>
    </main>
  );
}
