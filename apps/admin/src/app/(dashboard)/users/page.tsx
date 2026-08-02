"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { list, type UserListItem, type UserRole, type VerificationStatus } from "@/lib/api/admin-users";

const sb = createAdminBrowserClient();

const ROLES: { value: UserRole | ""; label: string }[] = [
  { value: "", label: "All roles" },
  { value: "passenger", label: "Passenger" },
  { value: "driver", label: "Driver" },
  { value: "admin", label: "Admin" },
];

const STATUSES: { value: VerificationStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "unverified", label: "Unverified" },
  { value: "pending_review", label: "Pending review" },
  { value: "verified", label: "Verified" },
  { value: "rejected", label: "Rejected" },
  { value: "suspended", label: "Suspended" },
];

const PAGE_SIZE = 20;

export default function UsersPage() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [status, setStatus] = useState<VerificationStatus | "">("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const timeout = setTimeout(async () => {
      try {
        const { data: session } = await sb.auth.getSession();
        const token = session.session?.access_token ?? "";
        const res = await list(token, {
          q: q.trim() || undefined,
          role: role || undefined,
          status: status || undefined,
          page,
        });
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
        }
      } catch {
        if (!cancelled) setError("Failed to load users.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [q, role, status, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="p-8 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Users ({total})</h1>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Search name or email…"
          className="border rounded px-3 py-1.5 text-sm w-64"
        />
        <select
          value={role}
          onChange={(e) => {
            setPage(1);
            setRole(e.target.value as UserRole | "");
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value as VerificationStatus | "");
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

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
          {items.map((u) => (
            <tr key={u.user_id} className="border-b hover:bg-gray-50">
              <td className="py-2 pr-4">{u.display_name || "—"}</td>
              <td className="py-2 pr-4 text-gray-600">{u.email}</td>
              <td className="py-2 pr-4 capitalize">{u.role}</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
                  u.verification_status === "verified" ? "bg-green-100 text-green-700" :
                  u.verification_status === "suspended" ? "bg-red-100 text-red-700" :
                  "bg-yellow-100 text-yellow-700"
                }`}>
                  {u.verification_status.replace(/_/g, " ")}
                </span>
              </td>
              <td className="py-2 flex gap-2">
                <Link href={`/users/${u.user_id}`} className="text-blue-600 hover:underline">
                  Detail
                </Link>
                {u.role === "driver" && (
                  <Link href={`/drivers/${u.user_id}/wallet`} className="text-green-600 hover:underline">
                    Wallet
                  </Link>
                )}
              </td>
            </tr>
          ))}
          {!loading && items.length === 0 && (
            <tr>
              <td colSpan={5} className="py-8 text-center text-gray-400">No users found</td>
            </tr>
          )}
        </tbody>
      </table>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="flex items-center gap-4 text-sm">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          className="text-blue-600 hover:underline disabled:text-gray-300 disabled:no-underline"
        >
          Previous
        </button>
        <span className="text-gray-500">Page {page} of {totalPages}</span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          className="text-blue-600 hover:underline disabled:text-gray-300 disabled:no-underline"
        >
          Next
        </button>
      </div>
    </main>
  );
}
