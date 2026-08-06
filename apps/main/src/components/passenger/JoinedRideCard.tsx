import Link from "next/link";
import { useTranslations } from "next-intl";

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

export function JoinedRideCard({
  href,
  departureLabel,
  originAddress,
  destinationAddress,
  status,
  driverName,
  price,
}: JoinedRideCardProps) {
  const t = useTranslations("joinedRideCard");
  const isMuted = status === "cancelled" || status === "completed";
  const STATUS_LABEL: Record<BookingStatus, string> = {
    pending: t("statusPending"),
    confirmed: t("statusConfirmed"),
    cancelled: t("statusCancelled"),
    completed: t("statusCompleted"),
  };

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
        {originAddress ?? t("unknownPlaceholder")} <span className="text-dash-text-muted">→</span>{" "}
        {destinationAddress ?? t("unknownPlaceholder")}
      </p>

      <div className="h-px bg-dash-border my-3" />

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-dash-text-muted truncate">
          {t("driverPrefix", { name: driverName ?? t("unknownPlaceholder") })}
        </p>
        <div className="text-end shrink-0">
          <p className="text-lg font-bold text-dash-navy">{price}</p>
          <p className="text-xs text-dash-text-muted">{t("total")}</p>
        </div>
      </div>
    </Link>
  );
}
