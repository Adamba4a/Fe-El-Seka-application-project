import type { RideStatus } from "@fe-el-seka/shared";

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled:   "bg-status-scheduled-bg text-status-scheduled",
  in_progress: "bg-status-in-progress-bg text-status-in-progress",
  completed:   "bg-status-completed-bg text-status-completed",
  cancelled:   "bg-status-cancelled-bg text-status-cancelled",
};

const STATUS_LABELS: Record<RideStatus, string> = {
  scheduled: "Scheduled",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function RideStatusBadge({ status }: { status: RideStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
