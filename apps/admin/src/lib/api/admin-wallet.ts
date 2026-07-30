const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface LedgerEntry {
  id: string;
  type: "COMMISSION_DEBIT" | "ADMIN_CREDIT" | "ADMIN_DEBIT";
  amount_egp: string;
  ride_id: string | null;
  booking_id: string | null;
  fuel_cost_egp_snapshot: string | null;
  created_by: string | null;
  note: string | null;
  created_at: string;
}

export interface WalletData {
  wallet_id: string;
  driver_id: string;
  balance_egp: string;
  reserved_egp: string;
  available_egp: string;
  entries: LedgerEntry[];
  pagination: {
    page: number;
    per_page: number;
    total_entries: number;
    total_pages: number;
  };
}

export async function getDriverWallet(
  token: string,
  driverId: string,
  page = 1,
): Promise<WalletData> {
  const res = await fetch(
    `${base}/api/admin/drivers/${driverId}/wallet?page=${page}`,
    { headers: authHeaders(token) },
  );
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function topupWallet(
  token: string,
  driverId: string,
  amount_egp: number,
  note?: string,
): Promise<{ new_balance_egp: string }> {
  const res = await fetch(`${base}/api/admin/drivers/${driverId}/wallet/topup`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ amount_egp, note: note || null }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function adjustWallet(
  token: string,
  driverId: string,
  amount_egp: number,
  note?: string,
): Promise<{ new_balance_egp: string }> {
  const res = await fetch(`${base}/api/admin/drivers/${driverId}/wallet/adjust`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ amount_egp, note: note || null }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
