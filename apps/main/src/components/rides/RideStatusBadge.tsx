import type { RideStatus } from "@fe-el-seka/shared";

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
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
