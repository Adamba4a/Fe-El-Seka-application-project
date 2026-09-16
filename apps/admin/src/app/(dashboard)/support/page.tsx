"use client";

import { useEffect, useState } from "react";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";

type Status = "open" | "in_progress" | "resolved";
type Report = {
  id: string; email: string; description: string; locale: string;
  status: Status; email_status: "pending" | "sent" | "failed"; created_at: string;
};
const labels: Record<Status, string> = { open: "Open", in_progress: "In progress", resolved: "Resolved" };

async function api(path: string, init?: RequestInit) {
  const { data } = await createAdminBrowserClient().auth.getSession();
  if (!data.session) throw new Error("Please sign in again.");
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/support${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${data.session.access_token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Unable to complete the request. Please retry.");
  return response.json();
}

export default function SupportPage() {
  const [items, setItems] = useState<Report[]>([]);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api(`?page=${page}${filter ? `&status=${filter}` : ""}`)
      .then((result) => { if (active) { setItems(result.items); setTotal(result.total); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filter, page, revision]);

  async function changeStatus(id: string, status: Status) {
    setSaving(id);
    setError("");
    try {
      await api(`/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      setRevision((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Update failed.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Support inbox</h1>
      <p className="text-sm text-gray-600">Signup and in-app problems. Reply using your support email. Submitted contact addresses are unverified.</p>
      <div className="flex flex-wrap items-center gap-4">
        <label>Status <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }} className="ml-2 rounded border p-2">
          <option value="">All</option>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <button onClick={() => setRevision((value) => value + 1)} className="rounded border px-4 py-2">Refresh</button>
      </div>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {loading ? <p role="status">Loading…</p> : !error && items.length === 0 ? <p>No support requests.</p> : !loading && !error && items.map((report) => (
        <article key={report.id} className="space-y-3 rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <a className="break-all text-blue-700 underline" href={`mailto:${encodeURIComponent(report.email)}`}>{report.email}</a>
            <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString()}</time>
          </div>
          <p dir="auto" className="whitespace-pre-wrap break-words">{report.description}</p>
          <p className="text-xs text-gray-600">Reference: {report.id} · Language: {report.locale.toUpperCase()} · Email: {report.email_status === "failed" ? "Failed after retries — report is still saved" : report.email_status}</p>
          <label className="block text-sm">Status
            <select aria-label={`Status for ${report.email}`} value={report.status} disabled={saving !== null}
              onChange={(e) => changeStatus(report.id, e.target.value as Status)} className="ml-2 rounded border p-2">
              {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </article>
      ))}
      <div className="flex items-center gap-4">
        <button disabled={page === 1 || loading} onClick={() => setPage(page - 1)} className="rounded border px-4 py-2 disabled:opacity-40">Previous</button>
        <span>Page {page} · {total} requests</span>
        <button disabled={page * 20 >= total || loading} onClick={() => setPage(page + 1)} className="rounded border px-4 py-2 disabled:opacity-40">Next</button>
      </div>
    </main>
  );
}
