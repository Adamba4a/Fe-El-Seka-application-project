import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Ride, Locale } from "@fe-el-seka/shared";
import { RideStatusBadge } from "./RideStatusBadge";

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

export function RideCard({ ride }: { ride: Ride }) {
  const t = useTranslations("driver.rides");
  const locale = useLocale() as Locale;
  return (
    <Link href={`/rides/${ride.id}/manage`} className="block">
      <div className="border border-border-default rounded-xl p-4 space-y-3 hover:border-brand-primary transition-colors bg-surface-card">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-content-primary truncate">{ride.origin.address}</p>
            <p className="text-xs text-content-muted mt-0.5">↓</p>
            <p className="text-sm font-medium text-content-primary truncate">{ride.destination.address}</p>
          </div>
          <RideStatusBadge status={ride.status} />
        </div>

        <div className="flex items-center justify-between text-xs text-content-muted">
          <span>{formatDate(ride.departure_datetime, locale)}</span>
          <span className="font-medium text-content-secondary">{formatCurrency(Number(ride.price_per_seat), locale)}{t("perSeatSuffix")}</span>
        </div>

        <div className="flex items-center gap-2 text-xs text-content-muted">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>{t("seatsAvailableCount", { available: ride.available_seats, total: ride.total_seats })}</span>
        </div>
      </div>
    </Link>
  );
}
