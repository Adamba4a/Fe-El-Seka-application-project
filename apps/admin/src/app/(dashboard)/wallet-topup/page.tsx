"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getQueue, approve, reject, type AdminTopupQueueItem } from "@/lib/api/admin-wallet-topup";

const sb = createAdminBrowserClient();

export default function WalletTopupQueuePage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminTopupQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actingOn, setActingOn] = useState<string | null>(null);
  const limit = 20;

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    try {
      const token = await getToken();
      const res = await getQueue(token, page);
      setItems(res.items);
      setTotal(res.total);
    } catch {
      setError("Failed to load top-up queue.");
    }
  }

  useEffect(() => {
    setError("");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function handleApprove(id: string) {
    if (!confirm("Approve this top-up request and credit the driver's wallet?")) return;
    setActingOn(id);
    setError("");
    try {
      const token = await getToken();
      await approve(token, id);
      setNotice("Request approved and wallet credited.");
      await load();
    } catch {
      setError("Failed to approve request.");
    } finally {
      setActingOn(null);
    }
  }

  async function handleReject(id: string) {
    const reason = prompt("Reason for rejection (required):");
    if (!reason || !reason.trim()) return;
    setActingOn(id);
    setError("");
    try {
      const token = await getToken();
      const res = await reject(token, id, reason.trim());
      setNotice(
        res.driver_locked
          ? "Request rejected. Driver has hit 3 rejections and is now locked from resubmitting."
          : "Request rejected."
      );
      await load();
    } catch {
      setError("Failed to reject request.");
    } finally {
      setActingOn(null);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
          <h1 className="text-2xl font-semibold">Wallet Top-Up Queue ({total})</h1>
        </div>
        <Link href="/wallet-topup/history" className="text-sm text-blue-600 hover:underline">
          View history
        </Link>
      </div>

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3">
          {notice}
        </div>
      )}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {items.length === 0 ? (
        <p className="text-gray-400 text-sm py-8 text-center">No pending top-up requests</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4 font-medium">Driver</th>
              <th className="pb-2 pr-4 font-medium">Email</th>
              <th className="pb-2 pr-4 font-medium">Amount (EGP)</th>
              <th className="pb-2 pr-4 font-medium">Reference</th>
              <th className="pb-2 pr-4 font-medium">Screenshot</th>
              <th className="pb-2 pr-4 font-medium">Submitted</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b">
                <td className="py-3 pr-4">{item.driver_name}</td>
                <td className="py-3 pr-4 text-gray-500">{item.driver_email}</td>
                <td className="py-3 pr-4">
                  {Number(item.amount_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })}
                </td>
                <td className="py-3 pr-4 text-gray-500">{item.payment_reference}</td>
                <td className="py-3 pr-4">
                  <a
                    href={item.screenshot_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View
                  </a>
                </td>
                <td className="py-3 pr-4 text-gray-500">
                  {new Date(item.created_at).toLocaleString("en-EG")}
                </td>
                <td className="py-3">
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleApprove(item.id)}
                      disabled={actingOn === item.id}
                      className="text-green-600 hover:underline disabled:text-gray-400"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(item.id)}
                      disabled={actingOn === item.id}
                      className="text-red-600 hover:underline disabled:text-gray-400"
                    >
                      Reject
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

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
