"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getQueue, fulfill, type AdminCarMaintenanceQueueItem } from "@/lib/api/admin-car-maintenance";

const sb = createAdminBrowserClient();

export default function CarMaintenanceQueuePage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminCarMaintenanceQueueItem[]>([]);
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
      setError("Failed to load car maintenance queue.");
    }
  }

  useEffect(() => {
    setError("");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function handleFulfill(id: string) {
    if (!confirm("Mark this reward as fulfilled? Only do this after the free maintenance has been arranged.")) return;
    setActingOn(id);
    setError("");
    try {
      const token = await getToken();
      await fulfill(token, id);
      setNotice("Reward marked as fulfilled.");
      await load();
    } catch {
      setError("Failed to fulfill reward.");
    } finally {
      setActingOn(null);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">Car Maintenance Rewards ({total})</h1>
      </div>

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3">
          {notice}
        </div>
      )}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {items.length === 0 ? (
        <p className="text-gray-400 text-sm py-8 text-center">No pending car maintenance rewards</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4 font-medium">Driver</th>
              <th className="pb-2 pr-4 font-medium">Email</th>
              <th className="pb-2 pr-4 font-medium">Amount (EGP)</th>
              <th className="pb-2 pr-4 font-medium">Reached</th>
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
                <td className="py-3 pr-4 text-gray-500">
                  {new Date(item.reached_at).toLocaleString("en-EG")}
                </td>
                <td className="py-3">
                  <button
                    onClick={() => handleFulfill(item.id)}
                    disabled={actingOn === item.id}
                    className="text-green-600 hover:underline disabled:text-gray-400"
                  >
                    Mark Fulfilled
                  </button>
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
