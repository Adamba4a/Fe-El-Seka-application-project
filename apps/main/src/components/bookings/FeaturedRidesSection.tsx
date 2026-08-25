"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Locale } from "@fe-el-seka/shared";
import type { FeaturedRide } from "@/lib/api/search";

function formatDeparture(iso: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

interface FeaturedRidesSectionProps {
  rides: FeaturedRide[];
  loading: boolean;
  error: string | null;
}

// Featured rides carry no driver/compatibility data (unlike search-matched
// candidates), so this renders a lighter card directly rather than reusing
// bookings/RideCard.tsx, which is built around that AI-matching shape.
export function FeaturedRidesSection({ rides, loading, error }: FeaturedRidesSectionProps) {
  const t = useTranslations("featuredRides");
  const tSeats = useTranslations("rideCard");
  const tPrice = useTranslations("availableRideCard");
  const locale = useLocale() as Locale;

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-bold text-dash-navy">{t("heading")}</h2>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      )}

      {!loading && error && (
        <p className="text-center py-8 text-sm text-content-destructive">{error}</p>
      )}

      {!loading && !error && rides.length === 0 && (
        <div className="text-center py-12 text-content-muted space-y-1">
          <p className="font-medium">{t("emptyTitle")}</p>
          <p className="text-sm">{t("emptyBody")}</p>
        </div>
      )}

      {!loading && !error && rides.length > 0 && (
        <div className="space-y-3">
          {rides.map((ride) => (
            <Link
              key={ride.ride_id}
              href={`/rides/${ride.ride_id}`}
              className="block bg-dash-surface rounded-2xl p-4 border border-dash-border"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold tracking-wide text-dash-primary">
                  {formatDeparture(ride.departure_datetime, locale)}
                </span>
                <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
                  {t("featuredBadge")}
                </span>
              </div>

              <p className="text-lg font-bold text-dash-navy mt-2">
                {ride.origin_address} <span className="text-dash-text-muted">→</span> {ride.destination_address}
              </p>

              <div className="h-px bg-dash-border my-3" />

              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-dash-text-muted">
                  {tSeats("seatsAvailable", { count: ride.available_seats })}
                </p>
                <div className="text-end shrink-0">
                  <p className="text-lg font-bold text-dash-navy">
                    {formatCurrency(Number(ride.price_per_seat), locale)}
                  </p>
                  <p className="text-xs text-dash-text-muted">{tPrice("perSeat")}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
