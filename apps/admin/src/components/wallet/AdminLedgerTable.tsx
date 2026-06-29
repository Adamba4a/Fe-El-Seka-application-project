import type { LedgerEntry } from "@/lib/api/admin-wallet";

interface Props {
  entries: LedgerEntry[];
}

const TYPE_LABELS: Record<LedgerEntry["type"], string> = {
  COMMISSION_DEBIT: "Commission",
  ADMIN_CREDIT: "Top-Up",
  ADMIN_DEBIT: "Adjustment",
};

const TYPE_COLORS: Record<LedgerEntry["type"], string> = {
  COMMISSION_DEBIT: "text-red-600",
  ADMIN_CREDIT: "text-green-600",
  ADMIN_DEBIT: "text-red-600",
};

const TYPE_SIGN: Record<LedgerEntry["type"], string> = {
  COMMISSION_DEBIT: "−",
  ADMIN_CREDIT: "+",
  ADMIN_DEBIT: "−",
};

function egp(value: string) {
  return new Intl.NumberFormat("en-EG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parseFloat(value));
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

export function AdminLedgerTable({ entries }: Props) {
  if (entries.length === 0) {
    return <p className="text-sm text-gray-400 py-4">No transactions yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-2 pr-4">Type</th>
            <th className="py-2 pr-4">Amount</th>
            <th className="py-2 pr-4">Ride</th>
            <th className="py-2 pr-4">Note</th>
            <th className="py-2">Date</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="border-b last:border-0">
              <td className="py-2 pr-4">
                <span className={`font-medium ${TYPE_COLORS[e.type]}`}>
                  {TYPE_LABELS[e.type]}
                </span>
              </td>
              <td className={`py-2 pr-4 font-mono ${TYPE_COLORS[e.type]}`}>
                {TYPE_SIGN[e.type]}{egp(e.amount_egp)} EGP
              </td>
              <td className="py-2 pr-4">
                {e.ride_id ? (
                  <span className="font-mono text-xs text-gray-500">
                    {e.ride_id.slice(0, 8)}…
                  </span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
              <td className="py-2 pr-4 text-gray-600 max-w-xs truncate">
                {e.note ?? <span className="text-gray-300">—</span>}
              </td>
              <td className="py-2 text-gray-500 whitespace-nowrap">{fmtDate(e.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
