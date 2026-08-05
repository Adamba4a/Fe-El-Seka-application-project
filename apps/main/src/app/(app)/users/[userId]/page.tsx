"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { createClient } from "@/lib/supabase/client";
import { getPublicProfile } from "@/lib/api/profiles";
import type { PublicProfile } from "@fe-el-seka/shared";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-EG", { year: "numeric", month: "short", day: "numeric" });
}

export default function PublicProfilePage() {
  const t = useTranslations("users.publicProfile");
  const params = useParams<{ userId: string }>();
  const userId = params.userId;
  const router = useRouter();

  const [profile, setProfile] = useState<PublicProfile | null>(null);
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
          ←
        </button>
        <h1 className="text-xl font-semibold text-content-primary">{t("heading")}</h1>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 flex items-center gap-4">
        {profile.profile_photo_url ? (
          <img
            src={profile.profile_photo_url}
            alt={profile.display_name}
            className="w-16 h-16 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-lg font-semibold text-content-secondary">
            {initials}
          </div>
        )}
        <div className="min-w-0">
          <p className="font-semibold text-content-primary truncate">{profile.display_name}</p>
          <div className="flex items-center gap-2 mt-1">
            {profile.verification_status === "verified" && (
              <span className="text-xs text-green-600 font-medium">{t("verifiedPrefix", { role: profile.role })}</span>
            )}
            <RatingBadge ratingAvg={profile.rating_avg} ratingCount={profile.rating_count} />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 flex items-center justify-between">
        <span className="text-sm text-content-muted">
          {profile.role === "driver" ? t("totalRidesDriven") : t("totalRidesTaken")}
        </span>
        <span className="text-sm font-semibold text-content-primary">{profile.total_rides}</span>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <p className="text-sm font-medium text-content-primary">{t("recentRides")}</p>
          {profile.recent_rides.length === 0 ? (
            <p className="text-sm text-content-muted">{t("noCompletedRides")}</p>
          ) : (
            profile.recent_rides.map((r, i) => (
              <div key={i} className="border-t border-border-default first:border-t-0 pt-3 first:pt-0 space-y-1">
                <p className="text-sm text-content-primary">
                  {r.origin_address ?? "—"} → {r.destination_address ?? "—"}
                </p>
                <p className="text-xs text-content-muted">{formatDate(r.departure_datetime)}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
