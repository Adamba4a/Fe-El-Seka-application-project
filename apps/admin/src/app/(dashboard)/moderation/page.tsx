"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@supabase/ssr";
import {
  getQueue,
  getFlagged,
  reviewReport,
  resolveReport,
  reinstateUser,
  type QueueReport,
  type FlaggedUser,
} from "@/lib/api/admin-moderation";
import { ResolveForm } from "@/components/moderation/ResolveForm";
import { ReinstateForm } from "@/components/moderation/ReinstateForm";

const sb = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

async function getToken(): Promise<string> {
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function ModerationPage() {
  const [reports, setReports] = useState<QueueReport[]>([]);
  const [flagged, setFlagged] = useState<FlaggedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const token = await getToken();
      const [queueRes, flaggedRes] = await Promise.all([
        getQueue(token),
        getFlagged(token),
      ]);
      setReports(queueRes.items);
      setFlagged(flaggedRes.items);
    } catch {
      setError("Failed to load moderation queue");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleReview(reportId: string) {
    const token = await getToken();
    const result = await reviewReport(token, reportId);
    setReports((prev) =>
      prev.map((r) => (r.report_id === reportId ? { ...r, status: result.status as "under_review" } : r))
    );
  }

  async function handleResolve(reportId: string, reportedUserId: string, action: "warn" | "suspend" | "dismiss", reason: string) {
    const token = await getToken();
    await resolveReport(token, reportId, action, reason);
    setReports((prev) => prev.filter((r) => r.report_id !== reportId));
    setNotice(
      action === "suspend"
        ? `Report resolved: user suspended. Use "Reinstate" below if this needs to be reversed.`
        : `Report ${action === "dismiss" ? "dismissed" : "resolved with a warning"}.`
    );
  }

  async function handleReinstate(userId: string, reason: string) {
    const token = await getToken();
    await reinstateUser(token, userId, reason);
    setNotice("User reinstated.");
    load();
  }

  if (loading) return <main className="p-8 text-gray-400">Loading…</main>;
  if (error) return <main className="p-8 text-red-600">{error}</main>;

  return (
    <main className="p-8 space-y-10 max-w-3xl">
      <h1 className="text-2xl font-semibold">Moderation</h1>

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3">
          {notice}
        </div>
      )}

      <section className="space-y-4">
        <h2 className="text-lg font-medium">Open Reports ({reports.length})</h2>
        {reports.length === 0 ? (
          <p className="text-sm text-gray-500">No open reports.</p>
        ) : (
          reports.map((r) => (
            <div key={r.report_id} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wide text-gray-500">{r.category.replace(/_/g, " ")}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{r.status.replace(/_/g, " ")}</span>
              </div>
              <p className="text-sm text-gray-800">{r.description}</p>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-gray-500">Reporter</dt><dd>{r.reporter.display_name}</dd>
                <dt className="text-gray-500">Reported user</dt><dd>{r.reported_user.display_name}</dd>
                <dt className="text-gray-500">Filed</dt><dd>{new Date(r.created_at).toLocaleString()}</dd>
              </dl>
              <div className="flex flex-wrap gap-3">
                {r.status === "open" && (
                  <button
                    onClick={() => handleReview(r.report_id)}
                    className="px-4 py-2 border rounded text-sm font-medium hover:bg-gray-50"
                  >
                    Mark Under Review
                  </button>
                )}
                <ResolveForm
                  onResolve={(action, reason) => handleResolve(r.report_id, r.reported_user.user_id, action, reason)}
                />
              </div>
            </div>
          ))
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-medium">Flagged Users ({flagged.length})</h2>
        <p className="text-xs text-gray-500">
          Advisory only — flagged users are not automatically actioned. Review their history before taking action.
        </p>
        {flagged.length === 0 ? (
          <p className="text-sm text-gray-500">No flagged users.</p>
        ) : (
          flagged.map((u) => (
            <div key={`${u.user_id}-${u.reason}`} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm">{u.display_name}</p>
                <span className="text-xs px-2 py-0.5 rounded bg-orange-100 text-orange-700">
                  {u.reason === "low_rating" ? "Low rating" : "Multiple reports"}
                </span>
              </div>
              <p className="text-sm text-gray-600">
                {u.reason === "low_rating"
                  ? `Recent average rating: ${u.rating_avg?.toFixed(2)}`
                  : `${u.recent_report_count} reports in the recent window`}
              </p>
              <ReinstateForm onReinstate={(reason) => handleReinstate(u.user_id, reason)} />
            </div>
          ))
        )}
      </section>
    </main>
  );
}
