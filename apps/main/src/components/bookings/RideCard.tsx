"use client";

import { MatchScoreBadge } from "@/components/search/MatchScoreBadge";

export interface RideCandidate {
  ride_id: string;
  driver: {
    display_name: string | null;
    avatar_url: string | null;
    is_verified: boolean;
  };
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  candidate_type: "standard" | "premium" | "nearby_endpoint";
  match_score_pct: number | null;
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

function formatDeparture(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
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
      <span className="text-xs text-content-muted w-10 text-right">{Math.round(clamped)}%</span>
    </div>
  );
}

interface RideCardProps {
  candidate: RideCandidate;
  onClick: (candidate: RideCandidate) => void;
}

export function RideCard({ candidate, onClick }: RideCardProps) {
  const isPremium = candidate.candidate_type === "premium";
  const isNearbyEndpoint = candidate.candidate_type === "nearby_endpoint";
  const totalPremiumFee =
    (candidate.compatibility.premium_pickup_fee ?? 0) +
    (candidate.compatibility.premium_dropoff_fee ?? 0);

  return (
    <button
      type="button"
      onClick={() => onClick(candidate)}
      className="w-full text-left"
    >
      <div className="border border-border-default rounded-xl p-4 space-y-3 hover:border-brand-primary transition-colors bg-surface-card">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {candidate.driver.avatar_url ? (
              <img
                src={candidate.driver.avatar_url}
                alt={candidate.driver.display_name ?? "Driver"}
                className="w-9 h-9 rounded-full object-cover shrink-0"
              />
            ) : (
              <div className="w-9 h-9 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-sm font-medium text-content-secondary">
                {(candidate.driver.display_name ?? "?")[0].toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-content-primary truncate">
                {candidate.driver.display_name ?? "Driver"}
              </p>
              <p className="text-xs text-content-muted">{formatDeparture(candidate.departure_datetime)}</p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1 shrink-0">
            {isPremium && (
              <span className="text-xs font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                PREMIUM
              </span>
            )}
            {isNearbyEndpoint && (
              <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                NEARBY DROP-OFF
              </span>
            )}
            <span className="text-sm font-semibold text-content-primary">
              EGP {candidate.per_seat_price}
              {isPremium && totalPremiumFee > 0 && (
                <span className="text-xs text-content-muted font-normal"> +{totalPremiumFee.toFixed(2)}</span>
              )}
            </span>
          </div>
        </div>

        {candidate.match_score_pct !== null && (
          <MatchScoreBadge score_pct={candidate.match_score_pct} />
        )}

        <OverlapBar pct={candidate.compatibility.overlap_percentage} />

        {isNearbyEndpoint && (
          <p className="text-xs text-blue-700 bg-blue-50 rounded-lg px-2 py-1.5">
            Driver ends ~{candidate.compatibility.nearby_endpoint_distance_km.toFixed(1)} km
            ({candidate.compatibility.nearby_endpoint_duration_minutes} min) from your destination —
            you&apos;ll need your own transport for the rest of the way.
          </p>
        )}

        <div className="flex items-center justify-between text-xs text-content-muted">
          <span>{candidate.available_seats} seat{candidate.available_seats !== 1 ? "s" : ""} available</span>
          <span>
            {Math.round(candidate.compatibility.pickup_walk_meters)}m walk to pickup
          </span>
        </div>
      </div>
    </button>
  );
}
