import Link from "next/link";
import { useState } from "react";

interface TripPassenger {
  display_name: string | null;
  avatar_url: string | null;
}

interface UpcomingTripCardProps {
  href: string;
  departureLabel: string;
  originAddress: string;
  destinationAddress: string;
  isFull: boolean;
  waitingCount: number;
  price: string;
  passengers: TripPassenger[];
}

function PassengerAvatar({ passenger }: { passenger: TripPassenger }) {
  const [broken, setBroken] = useState(false);
  if (passenger.avatar_url && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={passenger.avatar_url}
        alt={passenger.display_name ?? "Passenger"}
        className="w-8 h-8 rounded-full object-cover border-2 border-dash-surface"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className="w-8 h-8 rounded-full bg-dash-badge-bg text-dash-primary text-xs font-semibold flex items-center justify-center border-2 border-dash-surface">
      {(passenger.display_name ?? "?")[0]?.toUpperCase()}
    </div>
  );
}

export function UpcomingTripCard({
  href,
  departureLabel,
  originAddress,
  destinationAddress,
  isFull,
  waitingCount,
  price,
  passengers,
}: UpcomingTripCardProps) {
  return (
    <Link href={href} className="block bg-dash-surface rounded-2xl p-4 border border-dash-border">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-dash-primary">{departureLabel}</span>
        <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
          {isFull ? "CONFIRMED" : `PENDING (${waitingCount})`}
        </span>
      </div>

      <p className="text-lg font-bold text-dash-navy mt-2">
        {originAddress} <span className="text-dash-text-muted">→</span> {destinationAddress}
      </p>

      <div className="h-px bg-dash-border my-3" />

      <div className="flex items-center justify-between gap-3">
        {passengers.length > 0 ? (
          <div className="flex -space-x-2">
            {passengers.slice(0, 3).map((p, i) => (
              <PassengerAvatar key={i} passenger={p} />
            ))}
            {passengers.length > 3 && (
              <div className="w-8 h-8 rounded-full bg-dash-badge-bg text-dash-primary text-xs font-semibold flex items-center justify-center border-2 border-dash-surface">
                +{passengers.length - 3}
              </div>
            )}
          </div>
        ) : (
          <span className="text-sm text-dash-text-muted">Waiting for {waitingCount} more...</span>
        )}

        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-dash-navy">EGP {price}</p>
          <p className="text-xs text-dash-text-muted">Estimated Payout</p>
        </div>
      </div>
    </Link>
  );
}
