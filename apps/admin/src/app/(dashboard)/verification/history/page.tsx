"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getHistory, unlock, type HistoryItem } from "@/lib/api/admin-verification";

const sb = createAdminBrowserClient();

const OUTCOMES: { value: "" | "approved" | "rejected"; label: string }[] = [
  { value: "", label: "All outcomes" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export default function VerificationHistoryPage() {
  const [q, setQ] = useState("");
  const [outcome, setOutcome] = useState<"" | "approved" | "rejected">("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [unlocking, setUnlocking] = useState<string | null>(null);
  const limit = 20;

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    try {
      const token = await getToken();
      const res = await getHistory(token, page, q.trim() || undefined, outcome || undefined);
      setItems(res.items);
      setTotal(res.total);
    } catch {
      setError("Failed to load review history.");
    }
  }

  useEffect(() => {
    setError("");
    const timeout = setTimeout(load, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, outcome, page]);

  async function handleUnlock(userId: string) {
    if (!confirm("Unlock this user for re-submission?")) return;
    setUnlocking(userId);
    try {
      const token = await getToken();
      await unlock(token, userId);
      setNotice("User unlocked for re-submission.");
      await load();
    } catch {
      setError("Failed to unlock user.");
    } finally {
      setUnlocking(null);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/verification" className="text-sm text-blue-600 hover:underline">← Queue</Link>
        <h1 className="text-2xl font-semibold">Review History ({total})</h1>
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
          value={outcome}
          onChange={(e) => {
            setPage(1);
            setOutcome(e.target.value as "" | "approved" | "rejected");
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {OUTCOMES.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3">
          {notice}
        </div>
      )}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-2 pr-4 font-medium">User</th>
            <th className="pb-2 pr-4 font-medium">Outcome</th>
            <th className="pb-2 pr-4 font-medium">Reviewed At</th>
            <th className="pb-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.submission_id} className="border-b">
              <td className="py-3 pr-4">{row.user_name || "—"}</td>
              <td className="py-3 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${row.outcome === "approved" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {row.outcome}
                </span>
              </td>
              <td className="py-3 pr-4 text-gray-500">{row.reviewed_at ? new Date(row.reviewed_at).toLocaleString() : "—"}</td>
              <td className="py-3">
                {row.is_locked && (
                  <button
                    onClick={() => handleUnlock(row.user_id)}
                    disabled={unlocking === row.user_id}
                    className="text-blue-600 hover:underline disabled:text-gray-400"
                  >
                    {unlocking === row.user_id ? "Unlocking…" : "Unlock for re-submission"}
                  </button>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={4} className="py-8 text-center text-gray-400">No history yet</td></tr>
          )}
        </tbody>
      </table>

      <div className="flex gap-4 text-sm">
        {page > 1 && (
          <button onClick={() => setPage((p) => p - 1)} className="text-blue-600 hover:underline">
            Previous
          </button>
        )}
        {items.length === limit && (
          <button onClick={() => setPage((p) => p + 1)} className="text-blue-600 hover:underline">
            Next
          </button>
        )}
      </div>
    </main>
  );
}
