"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { listRides } from "@/lib/api/rides";
import { RideCard } from "@/components/rides/RideCard";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Ride, Locale } from "@fe-el-seka/shared";

function formatDate(iso: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

// A recurring definition can generate many day-instances; collapse them into
// one summary card here (deep-dive / per-day management lives on the
// dedicated /rides/recurring/[id] page) instead of flooding this list with
// a near-identical card per upcoming day.
function RecurringGroupCard({ definitionId, rides }: { definitionId: string; rides: Ride[] }) {
  const t = useTranslations("driver.rides");
  const tRecurring = useTranslations("driver.recurring");
  const locale = useLocale() as Locale;
  const next = [...rides].sort((a, b) => a.departure_datetime.localeCompare(b.departure_datetime))[0];

  return (
    <Link href={`/rides/recurring/${definitionId}`} className="block">
      <div className="border border-border-default rounded-xl p-4 space-y-3 hover:border-brand-primary transition-colors bg-surface-card">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-content-primary truncate">{next.origin.address}</p>
            <p className="text-xs text-content-muted mt-0.5">↓</p>
            <p className="text-sm font-medium text-content-primary truncate">{next.destination.address}</p>
          </div>
          <span className="inline-flex items-center rounded-full bg-brand-primary/10 text-brand-primary text-xs font-medium px-2 py-0.5 shrink-0">
            {tRecurring("seriesBadge")}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-content-muted">
          <span>{t("recurringNextDeparture", { date: formatDate(next.departure_datetime, locale) })}</span>
          <span className="font-medium text-content-secondary">
            {formatCurrency(Number(next.price_per_seat), locale)}{t("perSeatSuffix")}
          </span>
        </div>

        <div className="text-xs text-content-muted">{t("recurringUpcomingCount", { count: rides.length })}</div>
      </div>
    </Link>
  );
}

type RideListItem =
  | { type: "single"; ride: Ride }
  | { type: "group"; definitionId: string; rides: Ride[] };

function buildRideListItems(rides: Ride[]): RideListItem[] {
  const groups = new Map<string, Ride[]>();
  const singles: Ride[] = [];
  for (const ride of rides) {
    if (ride.recurring_ride_definition_id) {
      const arr = groups.get(ride.recurring_ride_definition_id) ?? [];
      arr.push(ride);
      groups.set(ride.recurring_ride_definition_id, arr);
    } else {
      singles.push(ride);
    }
  }

  const items: RideListItem[] = singles.map((ride) => ({ type: "single", ride }));
  for (const [definitionId, groupRides] of groups) {
    items.push({ type: "group", definitionId, rides: groupRides });
  }

  const earliest = (item: RideListItem) =>
    item.type === "single"
      ? item.ride.departure_datetime
      : item.rides.reduce(
          (min, r) => (r.departure_datetime < min ? r.departure_datetime : min),
          item.rides[0].departure_datetime
        );

  return items.sort((a, b) => earliest(a).localeCompare(earliest(b)));
}

export default function MyRidesPage() {
  const t = useTranslations("driver.rides");
  const tRecurring = useTranslations("driver.recurring");

  const TABS: { label: string; value: string }[] = [
    { label: t("tabAll"), value: "" },
    { label: t("tabScheduled"), value: "scheduled" },
    { label: t("tabInProgress"), value: "in_progress" },
    { label: t("tabCompleted"), value: "completed" },
    { label: t("tabCancelled"), value: "cancelled" },
  ];

  const [rides, setRides] = useState<Ride[]>([]);
  const [activeStatus, setActiveStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (status: string) => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const res = await listRides(session.access_token, { status: status || undefined });
      setRides(res.rides);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? t("loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(activeStatus);
  }, [activeStatus]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <div className="flex items-center gap-2">
          <Link
            href="/rides/recurring"
            className="border border-border-default hover:bg-surface-bg text-content-secondary text-body-sm font-medium px-4 py-2 rounded-xl transition-colors"
          >
            {tRecurring("manageLink")}
          </Link>
          <Link
            href="/rides/new"
            className="bg-dash-primary hover:opacity-90 text-content-inverse text-body-sm font-medium px-4 py-2 rounded-xl transition-opacity"
          >
            {t("postARide")}
          </Link>
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveStatus(tab.value)}
            className={`whitespace-nowrap px-3 py-1.5 rounded-full text-body-sm font-medium transition-colors ${
              activeStatus === tab.value
                ? "bg-dash-primary text-content-inverse"
                : "bg-surface-bg text-content-secondary hover:bg-border-default"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 bg-surface-bg rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <p className="text-body-sm text-content-destructive">{error}</p>
      )}

      {!loading && !error && rides.length === 0 && (
        <div className="text-center py-16 space-y-4">
          <div className="w-20 h-20 mx-auto bg-surface-bg rounded-full flex items-center justify-center">
            <svg className="w-10 h-10 text-content-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6-10l6-3m0 13l5.447-2.724A1 1 0 0021 16.382V5.618a1 1 0 00-1.447-.894L15 7m0 13V7" />
            </svg>
          </div>
          <h2 className="text-h3 text-content-primary">{t("noRidesTitle")}</h2>
          <p className="text-body-sm text-content-muted">{t("noRidesBody")}</p>
          <Link
            href="/rides/new"
            className="inline-block px-6 py-3 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium transition-opacity"
          >
            {t("postFirstRide")}
          </Link>
        </div>
      )}

      {!loading && rides.length > 0 && (
        <div className="space-y-3">
          {buildRideListItems(rides).map((item) =>
            item.type === "single" ? (
              <RideCard key={item.ride.id} ride={item.ride} />
            ) : (
              <RecurringGroupCard key={item.definitionId} definitionId={item.definitionId} rides={item.rides} />
            )
          )}
        </div>
      )}
    </div>
  );
}
