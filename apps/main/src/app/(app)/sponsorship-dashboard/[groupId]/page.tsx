"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { getSponsorshipDashboard } from "@/lib/api/groups";
import { formatEgp } from "@/lib/api/wallet";
import type { Locale, SponsorshipDashboard } from "@fe-el-seka/shared";

export default function SponsorshipDashboardPage() {
  const t = useTranslations("groups.sponsorshipDashboard");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const params = useParams<{ groupId: string }>();
  const groupId = params.groupId;

  const [dashboard, setDashboard] = useState<SponsorshipDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        const data = await getSponsorshipDashboard(session.access_token, groupId);
        setDashboard(data);
      } catch (err: any) {
        if (err?.error === "not_dashboard_contact") {
          setError(t("notContact"));
        } else if (err?.error === "group_not_found") {
          setError(t("notFound"));
        } else {
          setError(t("loadFailed"));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [groupId, router, t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("loadFailed")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-h3 text-content-primary truncate">{t("heading")}</h1>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
        <div className="text-center">
          <p className="text-body-sm text-content-muted mb-1">{t("fundedBalance")}</p>
          <p className="text-3xl font-bold text-brand-primary">
            {formatEgp(dashboard.funded_balance_egp, locale)}
          </p>
        </div>
        <div className="border-t border-border-default pt-3 text-center">
          <span className="text-caption text-content-muted">
            {t("memberCount", { count: dashboard.member_count })}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="text-label text-content-secondary">{t("activityHeading")}</h2>
        {dashboard.recent_activity.length === 0 ? (
          <p className="text-body-sm text-content-muted text-center py-8">{t("noActivity")}</p>
        ) : (
          <div className="space-y-2">
            {dashboard.recent_activity.map((item, idx) => (
              <div
                key={`${item.booking_id}-${idx}`}
                className="rounded-xl border border-border-default bg-surface-card p-3 flex items-center justify-between"
              >
                <div>
                  <p className="text-body-sm text-content-primary">
                    {item.type === "SPONSORED_RIDE_CREDIT" ? t("creditLabel") : t("reversalLabel")}
                  </p>
                  <p className="text-caption text-content-muted">
                    {new Date(item.created_at).toLocaleString(locale === "ar" ? "ar-EG" : "en-EG")}
                  </p>
                </div>
                <span
                  className={
                    item.type === "SPONSORED_RIDE_CREDIT"
                      ? "text-body-sm font-semibold text-content-primary"
                      : "text-body-sm font-semibold text-yellow-600"
                  }
                >
                  {item.type === "SPONSORED_RIDE_REVERSAL" ? "+" : "-"}
                  {formatEgp(item.amount_egp, locale)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
