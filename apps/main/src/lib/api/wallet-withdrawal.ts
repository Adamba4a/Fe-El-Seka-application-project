import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface WithdrawalSubmitResponse {
  id: string;
  status: string;
  amount_egp: string;
  payout_reference: string;
  created_at: string;
}

export interface WithdrawalHistoryItem {
  id: string;
  amount_egp: string;
  payout_reference: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface WithdrawalHistoryResponse {
  items: WithdrawalHistoryItem[];
  pagination: { page: number; per_page: number; total_entries: number; total_pages: number };
}

export async function submitWithdrawal(
  token: string,
  amountEgp: string,
  payoutReference: string,
): Promise<WithdrawalSubmitResponse> {
  const res = await fetch(`${base}/api/wallet/withdrawals`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ amount_egp: amountEgp, payout_reference: payoutReference }),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function getWithdrawalHistory(token: string, page = 1): Promise<WithdrawalHistoryResponse> {
  const res = await fetch(`${base}/api/wallet/withdrawals?page=${page}`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
