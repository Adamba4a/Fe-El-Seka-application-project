"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getQueue } from "@/lib/api/admin-verification";
import { SubmissionQueue } from "@/components/verification/SubmissionQueue";
import type { AdminQueueItem } from "@fe-el-seka/shared";

const sb = createAdminBrowserClient();

const TABS = ["all", "passenger_id", "driver_id", "vehicle"];

export default function VerificationQueuePage() {
  const [type, setType] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const limit = 20;

  useEffect(() => {
    let cancelled = false;
    setError("");
    const timeout = setTimeout(async () => {
      try {
        const { data: session } = await sb.auth.getSession();
        const token = session.session?.access_token ?? "";
        const res = await getQueue(token, type === "all" ? undefined : type, page, q.trim() || undefined);
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
        }
      } catch {
        if (!cancelled) setError("Failed to load verification queue.");
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [type, q, page]);

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Verification Queue ({total})</h1>
        <Link href="/verification/history" className="text-sm text-blue-600 hover:underline">
          View history
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-2">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => {
                setPage(1);
                setType(t);
              }}
              className={`px-3 py-1.5 rounded text-sm border capitalize ${
                type === t ? "bg-gray-900 text-white border-gray-900" : "bg-white hover:bg-gray-50"
              }`}
            >
              {t.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Search name or email…"
          className="border rounded px-3 py-1.5 text-sm w-64"
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <SubmissionQueue items={items} />

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
