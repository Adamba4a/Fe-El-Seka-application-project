import type { RideHistoryEntry } from "@fe-el-seka/shared";

const ACTION_LABELS: Record<string, string> = {
  created: "Ride created",
  edited: "Ride edited",
  cancelled: "Ride cancelled",
  started: "Ride started",
  completed: "Ride completed",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function RideHistoryLog({ history }: { history: RideHistoryEntry[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-gray-400">No history yet.</p>;
  }

  return (
    <ol className="space-y-4">
      {history.map((entry) => (
        <li key={entry.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span className="w-2 h-2 rounded-full bg-gray-400 mt-1.5" />
            <span className="flex-1 w-px bg-gray-200" />
          </div>
          <div className="pb-4 flex-1">
            <p className="text-sm font-medium text-gray-900">{ACTION_LABELS[entry.action] ?? entry.action}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {entry.actor_id ? "By driver" : "System"} · {formatDate(entry.created_at)}
            </p>
            {entry.reason && (
              <p className="text-sm text-gray-600 mt-1">Reason: {entry.reason}</p>
            )}
            {entry.changed_fields && Object.keys(entry.changed_fields).length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {Object.entries(entry.changed_fields).map(([field, diff]) => (
                  <li key={field} className="text-xs text-gray-500">
                    <span className="font-mono">{field}</span>: {String((diff as any).before)} → {String((diff as any).after)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
