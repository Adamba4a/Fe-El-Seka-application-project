import { createAdminClient } from "@/lib/supabase/admin-client";
import Link from "next/link";

export default async function DashboardPage() {
  const supabase = createAdminClient();

  const [pending, total] = await Promise.all([
    supabase.from("verification_submissions").select("id", { count: "exact", head: true }).eq("status", "pending_review"),
    supabase.from("profiles").select("id", { count: "exact", head: true }),
  ]);

  return (
    <main className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
      <div className="grid grid-cols-2 gap-4 max-w-lg">
        <Link href="/verification" className="block border rounded-lg p-5 hover:bg-gray-50">
          <p className="text-3xl font-bold">{pending.count ?? 0}</p>
          <p className="text-sm text-gray-500 mt-1">Pending verifications</p>
        </Link>
        <div className="border rounded-lg p-5">
          <p className="text-3xl font-bold">{total.count ?? 0}</p>
          <p className="text-sm text-gray-500 mt-1">Total users</p>
        </div>
      </div>
    </main>
  );
}
