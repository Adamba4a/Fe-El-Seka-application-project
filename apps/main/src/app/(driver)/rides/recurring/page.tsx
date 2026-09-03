"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { listRecurringDefinitions, utcTimeToLocalTime } from "@/lib/api/recurring-rides";
import { formatCurrency } from "@fe-el-seka/shared";
import type { RecurringRideDefinition, Locale } from "@fe-el-seka/shared";
import { fromIsoWeekday } from "@/lib/weekdays";

export default function RecurringRidesPage() {
  const t = useTranslations("driver.recurring");
  const locale = useLocale() as Locale;
  const [definitions, setDefinitions] = useState<RecurringRideDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const res = await listRecurringDefinitions(session.access_token);
        setDefinitions(res.definitions);
      } catch (err: any) {
        setError(err?.message ?? t("loadFailed"));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [t]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <Link
          href="/rides/new"
          className="bg-dash-primary hover:opacity-90 text-content-inverse text-body-sm font-medium px-4 py-2 rounded-xl transition-opacity"
        >
          {t("newRecurringRide")}
        </Link>
      </div>

      {loading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 bg-surface-bg rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && <p className="text-body-sm text-content-destructive">{error}</p>}

      {!loading && !error && definitions.length === 0 && (
        <div className="text-center py-16 space-y-4">
          <h2 className="text-h3 text-content-primary">{t("emptyTitle")}</h2>
          <p className="text-body-sm text-content-muted">{t("emptyBody")}</p>
          <Link
            href="/rides/new"
            className="inline-block px-6 py-3 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium transition-opacity"
          >
            {t("newRecurringRide")}
          </Link>
        </div>
      )}

      {!loading && definitions.length > 0 && (
        <div className="space-y-3">
          {definitions.map((def) => (
            <Link key={def.id} href={`/rides/recurring/${def.id}`} className="block">
              <div className="border border-border-default rounded-xl p-4 space-y-3 hover:border-brand-primary transition-colors bg-surface-card">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-content-primary truncate">{def.origin.address}</p>
                    <p className="text-xs text-content-muted mt-0.5">↓</p>
                    <p className="text-sm font-medium text-content-primary truncate">{def.destination.address}</p>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full text-xs font-medium px-2 py-0.5 shrink-0 ${
                      def.status === "active"
                        ? "bg-green-500/10 text-green-700"
                        : "bg-surface-bg text-content-muted"
                    }`}
                  >
                    {t(def.status === "active" ? "statusActive" : "statusEnded")}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-content-muted">
                  <span>
                    {utcTimeToLocalTime(def.departure_time.substring(0, 5))} ·{" "}
                    {def.weekdays.map((d) => t(`weekdayShort.${fromIsoWeekday(d)}`)).join(", ")}
                  </span>
                  <span className="font-medium text-content-secondary">
                    {formatCurrency(Number(def.price_per_seat), locale)}
                    {t("perSeatSuffix")}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
