"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { getSponsorshipDashboard, exportSponsorshipDashboardCsv } from "@/lib/api/groups";
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
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setExportError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const blob = await exportSponsorshipDashboardCsv(session.access_token, groupId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `sponsorship_${groupId}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setExportError(t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

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
        <h1 className="text-h3 text-content-primary truncate flex-1">{t("heading")}</h1>
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="text-body-sm text-brand-primary hover:underline disabled:text-content-muted whitespace-nowrap"
        >
          {exporting ? t("exporting") : t("exportCsv")}
        </button>
      </div>

      {exportError && <p className="text-caption text-content-destructive">{exportError}</p>}

      <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
        <div className="text-center">
          <p className="text-body-sm text-content-muted mb-1">{t("fundedBalance")}</p>
          <p className="text-3xl font-bold text-brand-primary">
            {formatEgp(dashboard.funded_balance_egp, locale)}
          </p>
        </div>
        <div className="border-t border-border-default pt-3 grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-lg font-semibold text-content-primary">
              {formatEgp(dashboard.total_paid_egp, locale)}
            </p>
            <p className="text-caption text-content-muted">{t("totalPaid")}</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-content-primary">{dashboard.total_rides}</p>
            <p className="text-caption text-content-muted">{t("totalRides")}</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-content-primary">{dashboard.member_count}</p>
            <p className="text-caption text-content-muted">{t("membersLabel")}</p>
          </div>
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
                className="rounded-xl border border-border-default bg-surface-card p-3 space-y-2"
              >
                <div className="flex items-center justify-between">
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
                <div className="border-t border-border-default pt-2 space-y-1 text-caption text-content-muted">
                  <p>
                    <span className="text-content-secondary">{t("driverLabel")}:</span>{" "}
                    {item.driver_name ?? t("unknownUser")}
                    {" · "}
                    <span className="text-content-secondary">{t("passengerLabel")}:</span>{" "}
                    {item.passenger_name ?? t("unknownUser")}
                  </p>
                  {(item.origin_address || item.destination_address) && (
                    <div className="space-y-0.5">
                      <p className="break-words">
                        <span className="text-content-secondary">{t("fromLabel")}:</span>{" "}
                        {item.origin_address ?? "?"}
                      </p>
                      <p className="break-words">
                        <span className="text-content-secondary">{t("toLabel")}:</span>{" "}
                        {item.destination_address ?? "?"}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
