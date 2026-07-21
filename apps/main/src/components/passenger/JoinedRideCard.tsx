import Link from "next/link";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface JoinedRideCardProps {
  href: string;
  departureLabel: string;
  originAddress: string | null;
  destinationAddress: string | null;
  status: BookingStatus;
  driverName: string | null;
  price: string;
}

const STATUS_LABEL: Record<BookingStatus, string> = {
  pending: "PENDING",
  confirmed: "CONFIRMED",
  cancelled: "CANCELLED",
  completed: "COMPLETED",
};

export function JoinedRideCard({
  href,
  departureLabel,
  originAddress,
  destinationAddress,
  status,
  driverName,
  price,
}: JoinedRideCardProps) {
  const isMuted = status === "cancelled" || status === "completed";

  return (
    <Link href={href} className="block bg-dash-surface rounded-2xl p-4 border border-dash-border">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-dash-primary">{departureLabel}</span>
        <span
          className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ${
            isMuted ? "bg-dash-bg text-dash-text-muted" : "bg-dash-badge-bg text-dash-primary"
          }`}
        >
          {STATUS_LABEL[status]}
        </span>
      </div>

      <p className="text-lg font-bold text-dash-navy mt-2">
        {originAddress ?? "—"} <span className="text-dash-text-muted">→</span> {destinationAddress ?? "—"}
      </p>

      <div className="h-px bg-dash-border my-3" />

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-dash-text-muted truncate">Driver: {driverName ?? "—"}</p>
        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-dash-navy">EGP {price}</p>
          <p className="text-xs text-dash-text-muted">total</p>
        </div>
      </div>
    </Link>
  );
}
