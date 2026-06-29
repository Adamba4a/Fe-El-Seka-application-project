import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export interface LedgerEntry {
  id: string;
  type: "COMMISSION_DEBIT" | "ADMIN_CREDIT" | "ADMIN_DEBIT";
  amount_egp: string;
  ride_id: string | null;
  booking_id: string | null;
  fuel_cost_egp_snapshot: string | null;
  note: string | null;
  created_at: string;
}

export interface WalletResponse {
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

export async function getWallet(token: string, page = 1): Promise<WalletResponse> {
  const res = await fetch(`${base}/api/v1/drivers/me/wallet?page=${page}`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export function formatEgp(amount: string | number): string {
  return new Intl.NumberFormat("en-EG", {
    style: "currency",
    currency: "EGP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(typeof amount === "string" ? parseFloat(amount) : amount);
}
