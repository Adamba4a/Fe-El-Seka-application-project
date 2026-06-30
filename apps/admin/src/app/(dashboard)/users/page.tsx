import { createAdminClient } from "@/lib/supabase/admin-client";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const supabase = createAdminClient();

  const { data: profiles } = await supabase
    .from("profiles")
    .select("id, display_name, email, role, verification_status")
    .order("role")
    .order("display_name");

  const users = profiles ?? [];

  return (
    <main className="p-8 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Users ({users.length})</h1>
      </div>

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-2 pr-4 font-medium">Name</th>
            <th className="py-2 pr-4 font-medium">Email</th>
            <th className="py-2 pr-4 font-medium">Role</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b hover:bg-gray-50">
              <td className="py-2 pr-4">{u.display_name || "—"}</td>
              <td className="py-2 pr-4 text-gray-600">{u.email}</td>
              <td className="py-2 pr-4 capitalize">{u.role}</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
                  u.verification_status === "verified" ? "bg-green-100 text-green-700" :
                  u.verification_status === "suspended" ? "bg-red-100 text-red-700" :
                  "bg-yellow-100 text-yellow-700"
                }`}>
                  {u.verification_status?.replace(/_/g, " ")}
                </span>
              </td>
              <td className="py-2 flex gap-2">
                <Link href={`/users/${u.id}`} className="text-blue-600 hover:underline">
                  Detail
                </Link>
                {u.role === "driver" && (
                  <Link href={`/drivers/${u.id}/wallet`} className="text-green-600 hover:underline">
                    Wallet
                  </Link>
                )}
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr>
              <td colSpan={5} className="py-8 text-center text-gray-400">No users yet</td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}
