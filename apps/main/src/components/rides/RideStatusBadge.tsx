import { useTranslations } from "next-intl";
import type { RideStatus } from "@fe-el-seka/shared";

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled:   "bg-status-scheduled-bg text-status-scheduled",
  in_progress: "bg-status-in-progress-bg text-status-in-progress",
  completed:   "bg-status-completed-bg text-status-completed",
  cancelled:   "bg-status-cancelled-bg text-status-cancelled",
};

const STATUS_KEYS: Record<RideStatus, "scheduled" | "inProgress" | "completed" | "cancelled"> = {
  scheduled: "scheduled",
  in_progress: "inProgress",
  completed: "completed",
  cancelled: "cancelled",
};

export function RideStatusBadge({ status }: { status: RideStatus }) {
  const t = useTranslations("rideStatus");
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {t(STATUS_KEYS[status])}
    </span>
  );
}
