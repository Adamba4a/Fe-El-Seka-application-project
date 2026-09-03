"use client";

import { useLocale, useTranslations } from "next-intl";
import { MatchScoreBadge } from "@/components/search/MatchScoreBadge";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Locale } from "@fe-el-seka/shared";

export interface RideCandidate {
  ride_id: string;
  driver: {
    display_name: string | null;
    avatar_url: string | null;
    is_verified: boolean;
    rating_avg: number | null;
    rating_count: number;
  };
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  candidate_type: "standard" | "premium" | "nearby_endpoint";
  match_score_pct: number | null;
  group_id?: string | null;
  group_name?: string | null;
  recurring_ride_definition_id?: string | null;
  recurring_dates_count?: number;
  compatibility: {
    overlap_percentage: number;
    pickup_walk_meters: number;
    dropoff_walk_meters: number;
    is_compatible: boolean;
    premium_pickup_available: boolean;
    premium_pickup_fee: number | null;
    premium_dropoff_available: boolean;
    premium_dropoff_fee: number | null;
    nearby_endpoint_available: boolean;
    nearby_endpoint_distance_km: number;
    nearby_endpoint_duration_minutes: number;
  };
}

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

function OverlapBar({ pct }: { pct: number }) {
  const clamped = Math.min(100, Math.max(0, pct));
  const color =
    clamped >= 70 ? "bg-green-500" : clamped >= 40 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-surface-bg rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${clamped}%` }} />
      </div>
      <span className="text-xs text-content-muted w-10 text-end">{Math.round(clamped)}%</span>
    </div>
  );
}

interface RideCardProps {
  candidate: RideCandidate;
  onClick: (candidate: RideCandidate) => void;
}

export function RideCard({ candidate, onClick }: RideCardProps) {
  const t = useTranslations("rideCard");
  const locale = useLocale() as Locale;
  const isPremium = candidate.candidate_type === "premium";
  const isNearbyEndpoint = candidate.candidate_type === "nearby_endpoint";
  const totalPremiumFee =
    (candidate.compatibility.premium_pickup_fee ?? 0) +
    (candidate.compatibility.premium_dropoff_fee ?? 0);

  return (
    <div className="rounded-2xl bg-dash-surface shadow-sm border border-dash-border p-5 space-y-4">
      <button
        type="button"
        onClick={() => onClick(candidate)}
        className="w-full text-start space-y-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {candidate.driver.avatar_url ? (
              <img
                src={candidate.driver.avatar_url}
                alt={candidate.driver.display_name ?? t("defaultDriverName")}
                className="w-11 h-11 rounded-full object-cover shrink-0"
              />
            ) : (
              <div className="w-11 h-11 rounded-full bg-dash-bg flex items-center justify-center shrink-0 text-sm font-semibold text-dash-navy">
                {(candidate.driver.display_name ?? "?")[0].toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="font-bold text-dash-navy truncate">
                {candidate.driver.display_name ?? t("defaultDriverName")}
              </p>
              <RatingBadge ratingAvg={candidate.driver.rating_avg} ratingCount={candidate.driver.rating_count} />
            </div>
          </div>

          <div className="flex flex-col items-end gap-1 shrink-0">
            {isPremium && (
              <span className="text-xs font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                {t("premium")}
              </span>
            )}
            {isNearbyEndpoint && (
              <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                {t("nearbyDropoff")}
              </span>
            )}
            <span className="text-xl font-bold text-dash-navy">
              {formatCurrency(Number(candidate.per_seat_price), locale)}
              {isPremium && totalPremiumFee > 0 && (
                <span className="text-xs text-dash-text-muted font-normal"> +{totalPremiumFee.toFixed(2)}</span>
              )}
            </span>
          </div>
        </div>

        {/* Route: two stops connected by a dashed line, real fields only */}
        <div className="flex gap-3">
          <div className="flex flex-col items-center pt-1">
            <span className="w-2.5 h-2.5 rounded-full border-2 border-dash-primary" />
            <span className="flex-1 w-px border-s border-dashed border-dash-border my-1" />
            <span className="w-2.5 h-2.5 rounded-full bg-dash-text-muted" />
          </div>
          <div className="flex-1 space-y-3 min-w-0">
            <div>
              <p className="text-sm font-medium text-dash-navy">{formatDeparture(candidate.departure_datetime, locale)}</p>
              <p className="text-xs text-dash-text-muted">
                {t("walkToPickup", { meters: Math.round(candidate.compatibility.pickup_walk_meters) })}
              </p>
            </div>
            <div>
              <p className="text-xs text-dash-text-muted">
                {t("seatsAvailable", { count: candidate.available_seats })}
              </p>
            </div>
          </div>
        </div>

        {candidate.group_name && (
          <span className="inline-block text-xs font-semibold bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
            {t("groupRide", { name: candidate.group_name })}
          </span>
        )}

        {candidate.recurring_ride_definition_id && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full">
            {t("recurringBadge")}
            {candidate.recurring_dates_count && candidate.recurring_dates_count > 1 && (
              <span className="font-normal">
                · {t("recurringDatesAvailable", { count: candidate.recurring_dates_count })}
              </span>
            )}
          </span>
        )}

        {candidate.match_score_pct !== null && (
          <MatchScoreBadge score_pct={candidate.match_score_pct} />
        )}

        <OverlapBar pct={candidate.compatibility.overlap_percentage} />

        {isNearbyEndpoint && (
          <p className="text-xs text-blue-700 bg-blue-50 rounded-lg px-2 py-1.5">
            {t("nearbyEndpointNote", {
              distance: candidate.compatibility.nearby_endpoint_distance_km.toFixed(1),
              duration: candidate.compatibility.nearby_endpoint_duration_minutes,
            })}
          </p>
        )}
      </button>

      <button
        type="button"
        onClick={() => onClick(candidate)}
        className="w-full rounded-full bg-dash-primary hover:opacity-90 text-white py-2.5 text-sm font-semibold transition-opacity"
      >
        {t("book")}
      </button>
    </div>
  );
}
