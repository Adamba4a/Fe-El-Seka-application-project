import { useState } from "react";

interface AvailableRideCardProps {
  onJoin: () => void;
  departureLabel: string;
  originAddress: string;
  destinationAddress: string;
  price: string;
  distanceLabel: string;
  driverName: string | null;
  driverAvatarUrl: string | null;
  isVerified: boolean;
}

function DriverAvatar({ name, avatarUrl }: { name: string | null; avatarUrl: string | null }) {
  const [broken, setBroken] = useState(false);
  if (avatarUrl && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={avatarUrl}
        alt={name ?? "Driver"}
        className="w-9 h-9 rounded-full object-cover"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className="w-9 h-9 rounded-full bg-dash-badge-bg text-dash-primary text-sm font-semibold flex items-center justify-center">
      {(name ?? "?")[0]?.toUpperCase()}
    </div>
  );
}

export function AvailableRideCard({
  onJoin,
  departureLabel,
  originAddress,
  destinationAddress,
  price,
  distanceLabel,
  driverName,
  driverAvatarUrl,
  isVerified,
}: AvailableRideCardProps) {
  return (
    <div className="bg-dash-surface rounded-2xl p-4 border border-dash-border">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-dash-primary">{departureLabel}</span>
        <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
          {distanceLabel}
        </span>
      </div>

      <p className="text-lg font-bold text-dash-navy mt-2">
        {originAddress} <span className="text-dash-text-muted">→</span> {destinationAddress}
      </p>

      <div className="h-px bg-dash-border my-3" />

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <DriverAvatar name={driverName} avatarUrl={driverAvatarUrl} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-dash-navy truncate">{driverName ?? "Driver"}</p>
            {isVerified && <p className="text-xs text-dash-primary">Verified driver</p>}
          </div>
        </div>

        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-dash-navy">EGP {price}</p>
          <p className="text-xs text-dash-text-muted">per seat</p>
        </div>
      </div>

      <button
        type="button"
        onClick={onJoin}
        className="mt-3 block w-full text-center rounded-xl bg-dash-primary text-white font-semibold py-2.5"
      >
        Join Ride
      </button>
    </div>
  );
}
