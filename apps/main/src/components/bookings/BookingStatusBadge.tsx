"use client";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

const STATUS_CONFIG: Record<BookingStatus, { label: string; className: string }> = {
  pending: {
    label: "Awaiting Confirmation",
    className: "bg-amber-100 text-amber-800 border-amber-200",
  },
  confirmed: {
    label: "Confirmed",
    className: "bg-green-100 text-green-800 border-green-200",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-red-100 text-red-800 border-red-200",
  },
  completed: {
    label: "Completed",
    className: "bg-gray-100 text-gray-600 border-gray-200",
  },
};

interface BookingStatusBadgeProps {
  status: BookingStatus;
}

export function BookingStatusBadge({ status }: BookingStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.cancelled;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${config.className}`}
    >
      {config.label}
    </span>
  );
}
