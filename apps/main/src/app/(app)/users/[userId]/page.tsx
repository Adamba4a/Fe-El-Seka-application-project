"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { createClient } from "@/lib/supabase/client";
import { getPublicProfile } from "@/lib/api/profiles";
import { formatDate } from "@fe-el-seka/shared";
import type { Locale, PublicProfile } from "@fe-el-seka/shared";

interface RatingComment {
  comment: string;
  created_at: string;
}

export default function PublicProfilePage() {
  const t = useTranslations("users.publicProfile");
  const locale = useLocale() as Locale;
  const params = useParams<{ userId: string }>();
  const userId = params.userId;
  const router = useRouter();

  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [comments, setComments] = useState<RatingComment[]>([]);
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
        setProfile(await getPublicProfile(session.access_token, userId));

        const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${base}/api/profiles/${userId}/rating`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const summary = await res.json();
          setComments(summary.comments ?? []);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : t("loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("notFound")}</p>
      </div>
    );
  }

  const initials = (profile.display_name || "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="max-w-md mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-xl font-semibold text-content-primary">{t("heading")}</h1>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 flex flex-col items-center text-center gap-3">
        {profile.profile_photo_url ? (
          <img
            src={profile.profile_photo_url}
            alt={profile.display_name}
            className="w-24 h-24 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-24 h-24 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-2xl font-semibold text-content-secondary">
            {initials}
          </div>
        )}
        <p className="text-lg font-bold text-content-primary">{profile.display_name}</p>
        <div className="flex items-center gap-2 flex-wrap justify-center">
          {profile.verification_status === "verified" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-700 text-xs font-medium px-2.5 py-1">
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M10 1.5l2.6 1.3 2.9-.3 1 2.7 2.5 1.6-1 2.7 1 2.7-2.5 1.6-1 2.7-2.9-.3L10 18.5l-2.6-1.3-2.9.3-1-2.7-2.5-1.6 1-2.7-1-2.7 2.5-1.6 1-2.7 2.9.3L10 1.5z"
                />
                <path
                  fillRule="evenodd"
                  d="M13.2 8.2a.75.75 0 00-1.1-1L9 10.3 7.9 9.2a.75.75 0 10-1.1 1l1.8 1.8c.3.3.8.3 1.1 0l3.5-3.8z"
                  fill="white"
                />
              </svg>
              {t("verifiedPrefix", { role: profile.role })}
            </span>
          )}
          <RatingBadge ratingAvg={profile.rating_avg} ratingCount={profile.rating_count} />
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 flex items-center justify-between">
        <span className="text-sm text-content-muted">
          {profile.role === "driver" ? t("totalRidesDriven") : t("totalRidesTaken")}
        </span>
        <span className="text-sm font-semibold text-content-primary">{profile.total_rides}</span>
      </div>

      {profile.phone_number && (
        <a
          href={`tel:${profile.phone_number}`}
          className="rounded-xl border border-border-default bg-surface-card p-4 flex items-center justify-between hover:bg-surface-bg transition-colors"
        >
          <span className="flex items-center gap-2 text-sm text-content-muted">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-brand-primary" aria-hidden="true">
              <path d="M3.5 2.5a1 1 0 011-1h2.2a1 1 0 01.98.8l.6 3a1 1 0 01-.5 1.08l-1.3.7a11.4 11.4 0 005.4 5.4l.7-1.3a1 1 0 011.08-.5l3 .6a1 1 0 01.8.98v2.2a1 1 0 01-1 1h-1C7.9 15.48 4.52 12.1 3.5 5.5v-3z" />
            </svg>
            {t("phoneLabel")}
          </span>
          <span className="text-sm font-semibold text-brand-primary" dir="ltr">
            {profile.phone_number}
          </span>
        </a>
      )}

      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <p className="text-sm font-medium text-content-primary">{t("recentRides")}</p>
          {profile.recent_rides.length === 0 ? (
            <p className="text-sm text-content-muted">{t("noCompletedRides")}</p>
          ) : (
            profile.recent_rides.map((r, i) => (
              <div key={i} className="border-t border-border-default first:border-t-0 pt-3 first:pt-0">
                <div className="flex gap-3">
                  <div className="flex flex-col items-center pt-1">
                    <span className="w-2 h-2 rounded-full bg-content-muted shrink-0" aria-hidden="true" />
                    <span className="w-px flex-1 bg-border-default my-1" aria-hidden="true" />
                    <span className="w-2 h-2 bg-brand-primary shrink-0" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0 space-y-3 pb-0.5">
                    <p className="text-sm text-content-primary">{r.origin_address ?? "—"}</p>
                    <p className="text-sm text-content-primary">{r.destination_address ?? "—"}</p>
                  </div>
                </div>
                <p className="text-xs text-content-muted mt-2">
                  {r.departure_datetime ? formatDate(r.departure_datetime, locale) : "—"}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <p className="text-sm font-medium text-content-primary">{t("commentsLabel")}</p>
          {comments.length === 0 ? (
            <p className="text-sm text-content-muted">{t("noComments")}</p>
          ) : (
            comments.map((c, i) => (
              <div key={i} className="border-t border-border-default first:border-t-0 pt-3 first:pt-0 space-y-1">
                <p className="text-sm text-content-primary">{c.comment}</p>
                <p className="text-xs text-content-muted">{formatDate(c.created_at, locale)}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
