import type { RideHistoryEntry } from "@fe-el-seka/shared";

const ACTION_LABELS: Record<string, string> = {
  created:   "Ride created",
  edited:    "Ride edited",
  cancelled: "Ride cancelled",
  started:   "Ride started",
  completed: "Ride completed",
};

const ACTION_DOT_COLORS: Record<string, string> = {
  created:   "bg-status-completed",
  edited:    "bg-status-scheduled",
  started:   "bg-status-in-progress",
  completed: "bg-status-completed",
  cancelled: "bg-status-cancelled",
};

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatAbsoluteTime(iso: string): string {
  return new Date(iso).toLocaleString("en-EG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function RideHistoryLog({ entries }: { entries: RideHistoryEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-body-sm text-content-muted">No history yet.</p>;
  }

  const sorted = [...entries].reverse();

  return (
    <ol className="space-y-4">
      {sorted.map((entry, i) => {
        const dotColor = ACTION_DOT_COLORS[entry.action] ?? "bg-content-muted";
        const actor = entry.actor_id ? "Driver" : "System";
        const changedKeys = entry.changed_fields
          ? Object.keys(entry.changed_fields)
          : null;

        return (
          <li key={entry.id} className="flex gap-3">
            <div className="flex flex-col items-center flex-shrink-0">
              <span className={`w-2 h-2 rounded-full mt-1.5 ${dotColor}`} />
              {i < sorted.length - 1 && (
                <span className="flex-1 w-px bg-border-default mt-1" />
              )}
            </div>

            <div className="pb-4 flex-1 min-w-0">
              <p className="text-body-sm font-medium text-content-primary">
                {ACTION_LABELS[entry.action] ?? entry.action}
              </p>
              <p className="text-caption text-content-muted mt-0.5">
                {actor}
                {" · "}
                <span title={formatAbsoluteTime(entry.created_at)}>
                  {formatRelativeTime(entry.created_at)}
                </span>
              </p>
              {changedKeys && changedKeys.length > 0 && (
                <p className="text-caption text-content-secondary mt-1">
                  Changed: {changedKeys.join(", ")}
                </p>
              )}
              {entry.reason && (
                <p className="text-body-sm text-content-secondary mt-1">
                  Reason: {entry.reason}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
