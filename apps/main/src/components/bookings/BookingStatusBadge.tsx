"use client";

import { useTranslations } from "next-intl";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

const STATUS_CLASSNAMES: Record<BookingStatus, string> = {
  pending: "bg-status-in-progress-bg text-status-in-progress border-transparent",
  confirmed: "bg-status-completed-bg text-status-completed border-transparent",
  cancelled: "bg-status-cancelled-bg text-status-cancelled border-transparent",
  completed: "bg-surface-bg text-content-muted border-transparent",
};

interface BookingStatusBadgeProps {
  status: BookingStatus;
}

export function BookingStatusBadge({ status }: BookingStatusBadgeProps) {
  const t = useTranslations("bookingStatus");
  const className = STATUS_CLASSNAMES[status] ?? STATUS_CLASSNAMES.cancelled;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {t(status)}
    </span>
  );
}
