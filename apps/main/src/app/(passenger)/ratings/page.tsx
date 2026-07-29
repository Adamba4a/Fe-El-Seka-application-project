"use client";

import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { getMe } from "@/lib/api/profiles";

interface RatingComment {
  comment: string;
  created_at: string;
}

interface RatingSummary {
  rating_avg: number | null;
  rating_count: number;
  comments: RatingComment[];
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-EG", { year: "numeric", month: "short", day: "numeric" });
}

export default function PassengerRatingSummaryPage() {
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) throw new Error("Not signed in");
        const me = await getMe(session.access_token);
        const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${base}/api/profiles/${me.id}/rating`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (!res.ok) throw new Error("Failed to load rating summary");
        setSummary(await res.json());
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load rating summary");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? "Failed to load rating summary"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <h1 className="text-xl font-semibold text-content-primary">My Rating</h1>

      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 flex items-center gap-4">
          <div className="text-3xl font-bold text-content-primary">
            {summary.rating_avg !== null ? summary.rating_avg.toFixed(2) : "—"}
          </div>
          <div>
            <p className="text-amber-400 text-lg leading-none">
              {"★".repeat(Math.round(summary.rating_avg ?? 0))}
              <span className="text-border-default">
                {"★".repeat(5 - Math.round(summary.rating_avg ?? 0))}
              </span>
            </p>
            <p className="text-xs text-content-muted mt-1">
              {summary.rating_count} rating{summary.rating_count === 1 ? "" : "s"}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <p className="text-sm font-medium text-content-primary">Comments</p>
          {summary.comments.length === 0 ? (
            <p className="text-sm text-content-muted">No comments yet.</p>
          ) : (
            summary.comments.map((c, i) => (
              <div key={i} className="border-t border-border-default first:border-t-0 pt-3 first:pt-0 space-y-1">
                <p className="text-sm text-content-primary">{c.comment}</p>
                <p className="text-xs text-content-muted">{formatDate(c.created_at)}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
