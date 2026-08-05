"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { listRides } from "@/lib/api/rides";
import { RideCard } from "@/components/rides/RideCard";
import type { Ride } from "@fe-el-seka/shared";

export default function MyRidesPage() {
  const t = useTranslations("driver.rides");

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
    } catch {
      setError(t("loadFailed"));
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
        <Link
          href="/rides/new"
          className="bg-brand-primary hover:bg-brand-primary-hover text-content-inverse text-body-sm font-medium px-4 py-2 rounded-xl transition-colors"
        >
          {t("postARide")}
        </Link>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveStatus(tab.value)}
            className={`whitespace-nowrap px-3 py-1.5 rounded-full text-body-sm font-medium transition-colors ${
              activeStatus === tab.value
                ? "bg-brand-primary text-content-inverse"
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
            className="inline-block px-6 py-3 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium transition-colors"
          >
            {t("postFirstRide")}
          </Link>
        </div>
      )}

      {!loading && rides.length > 0 && (
        <div className="space-y-3">
          {rides.map((ride) => (
            <RideCard key={ride.id} ride={ride} />
          ))}
        </div>
      )}
    </div>
  );
}
