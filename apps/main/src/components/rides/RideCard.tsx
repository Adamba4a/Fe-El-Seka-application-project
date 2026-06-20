import Link from "next/link";
import type { Ride } from "@fe-el-seka/shared";
import { RideStatusBadge } from "./RideStatusBadge";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RideCard({ ride }: { ride: Ride }) {
  return (
    <Link href={`/rides/${ride.id}`} className="block">
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
          <span>{formatDate(ride.departure_datetime)}</span>
          <span className="font-medium text-content-secondary">EGP {ride.price_per_seat}/seat</span>
        </div>

        <div className="flex items-center gap-2 text-xs text-content-muted">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>{ride.available_seats}/{ride.total_seats} seats available</span>
        </div>
      </div>
    </Link>
  );
}
