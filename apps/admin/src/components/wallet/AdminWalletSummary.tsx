interface Props {
  balance_egp: string;
  reserved_egp: string;
  available_egp: string;
  sponsored_earnings_egp?: string;
}

function egp(value: string) {
  return new Intl.NumberFormat("en-EG", {
    style: "currency",
    currency: "EGP",
    minimumFractionDigits: 2,
  }).format(parseFloat(value));
}

export function AdminWalletSummary({
  balance_egp,
  reserved_egp,
  available_egp,
  sponsored_earnings_egp,
}: Props) {
  return (
    <div className={`grid gap-4 ${sponsored_earnings_egp !== undefined ? "grid-cols-4" : "grid-cols-3"}`}>
      <div className="rounded border p-4 text-center">
        <p className="text-xs text-gray-500 mb-1">Cash Balance</p>
        <p className="text-lg font-semibold">{egp(balance_egp)}</p>
      </div>
      <div className="rounded border p-4 text-center">
        <p className="text-xs text-gray-500 mb-1">Reserved</p>
        <p className="text-lg font-semibold text-yellow-600">{egp(reserved_egp)}</p>
      </div>
      <div className="rounded border p-4 text-center">
        <p className="text-xs text-gray-500 mb-1">Available</p>
        <p className="text-lg font-semibold text-green-600">{egp(available_egp)}</p>
      </div>
      {sponsored_earnings_egp !== undefined && (
        <div className="rounded border p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Sponsored Earnings</p>
          <p className="text-lg font-semibold text-blue-600">{egp(sponsored_earnings_egp)}</p>
        </div>
      )}
    </div>
  );
}
