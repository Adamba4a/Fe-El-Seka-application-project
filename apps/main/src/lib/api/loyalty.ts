import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export interface LoyaltyBalance {
  account_id: string;
  role: "passenger" | "driver";
  balance: number;
}

export interface LoyaltyTransaction {
  id: string;
  delta: number;
  reason: string;
  balance_after: number;
  ride_id: string | null;
  booking_id: string | null;
  redemption_request_id: string | null;
  created_at: string;
}

export interface LoyaltyTransactionsResponse {
  items: LoyaltyTransaction[];
  total: number;
  page: number;
}

export interface LoyaltyCatalogEntry {
  id: string;
  type: string;
  title: string;
  description: string;
  point_cost: number;
  fulfillment_mode: string;
}

export interface LoyaltyCatalogResponse {
  items: LoyaltyCatalogEntry[];
}

export async function getLoyaltyBalance(token: string): Promise<LoyaltyBalance> {
  const res = await fetch(`${base}/api/v1/loyalty/balance`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function getLoyaltyTransactions(token: string, page = 1): Promise<LoyaltyTransactionsResponse> {
  const res = await fetch(`${base}/api/v1/loyalty/transactions?page=${page}`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function getLoyaltyCatalog(token: string): Promise<LoyaltyCatalogResponse> {
  const res = await fetch(`${base}/api/v1/loyalty/catalog`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
