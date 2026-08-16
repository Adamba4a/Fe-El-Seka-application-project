"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getHistory, unlock, type AdminTopupHistoryItem } from "@/lib/api/admin-wallet-topup";

const sb = createAdminBrowserClient();

const OUTCOMES: { value: "" | "APPROVED" | "REJECTED"; label: string }[] = [
  { value: "", label: "All outcomes" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
];

export default function WalletTopupHistoryPage() {
  const [q, setQ] = useState("");
  const [outcome, setOutcome] = useState<"" | "APPROVED" | "REJECTED">("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminTopupHistoryItem[]>([]);
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
      const res = await getHistory(token, page, outcome || undefined, q.trim() || undefined);
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

  async function handleUnlock(driverId: string) {
    if (!confirm("Unlock this driver for re-submission?")) return;
    setUnlocking(driverId);
    try {
      const token = await getToken();
      await unlock(token, driverId);
      setNotice("Driver unlocked for re-submission.");
      await load();
    } catch {
      setError("Failed to unlock driver.");
    } finally {
      setUnlocking(null);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/wallet-topup" className="text-sm text-blue-600 hover:underline">← Queue</Link>
        <h1 className="text-2xl font-semibold">Top-Up Review History ({total})</h1>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Search driver name…"
          className="border rounded px-3 py-1.5 text-sm w-64"
        />
        <select
          value={outcome}
          onChange={(e) => {
            setPage(1);
            setOutcome(e.target.value as "" | "APPROVED" | "REJECTED");
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
            <th className="pb-2 pr-4 font-medium">Driver</th>
            <th className="pb-2 pr-4 font-medium">Amount (EGP)</th>
            <th className="pb-2 pr-4 font-medium">Outcome</th>
            <th className="pb-2 pr-4 font-medium">Reason</th>
            <th className="pb-2 pr-4 font-medium">Reviewed At</th>
            <th className="pb-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.request_id} className="border-b">
              <td className="py-3 pr-4">{row.driver_name || "—"}</td>
              <td className="py-3 pr-4">
                {Number(row.amount_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })}
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    row.status === "APPROVED" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                  }`}
                >
                  {row.status}
                </span>
              </td>
              <td className="py-3 pr-4 text-gray-500">{row.rejection_reason || "—"}</td>
              <td className="py-3 pr-4 text-gray-500">
                {row.reviewed_at ? new Date(row.reviewed_at).toLocaleString("en-EG") : "—"}
              </td>
              <td className="py-3">
                {row.driver_is_locked && (
                  <button
                    onClick={() => handleUnlock(row.driver_id)}
                    disabled={unlocking === row.driver_id}
                    className="text-blue-600 hover:underline disabled:text-gray-400"
                  >
                    {unlocking === row.driver_id ? "Unlocking…" : "Unlock for re-submission"}
                  </button>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={6} className="py-8 text-center text-gray-400">No history yet</td></tr>
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
