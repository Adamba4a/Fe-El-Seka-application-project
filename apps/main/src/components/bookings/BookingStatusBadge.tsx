"use client";

import { useTranslations } from "next-intl";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

const STATUS_CLASSNAMES: Record<BookingStatus, string> = {
  pending: "bg-amber-100 text-amber-800 border-amber-200",
  confirmed: "bg-green-100 text-green-800 border-green-200",
  cancelled: "bg-red-100 text-red-800 border-red-200",
  completed: "bg-gray-100 text-gray-600 border-gray-200",
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
