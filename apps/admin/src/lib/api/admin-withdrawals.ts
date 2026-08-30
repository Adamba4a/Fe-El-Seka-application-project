const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface AdminWithdrawalQueueItem {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string;
  amount_egp: string;
  payout_reference: string;
  created_at: string;
}

export interface AdminWithdrawalQueueResponse {
  total: number;
  page: number;
  items: AdminWithdrawalQueueItem[];
}

export interface AdminWithdrawalHistoryItem {
  request_id: string;
  driver_id: string;
  driver_name: string;
  amount_egp: string;
  status: "APPROVED" | "REJECTED";
  rejection_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface AdminWithdrawalHistoryResponse {
  total: number;
  page: number;
  items: AdminWithdrawalHistoryItem[];
}

export interface AdminWithdrawalApproveResponse {
  id: string;
  status: string;
  ledger_entry_id: string;
  new_balance_egp: string;
  reviewed_by: string;
  reviewed_at: string;
}

export interface AdminWithdrawalRejectResponse {
  id: string;
  status: string;
  rejection_reason: string;
  reviewed_by: string;
  reviewed_at: string;
}

export async function getQueue(token: string, page = 1): Promise<AdminWithdrawalQueueResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  const res = await fetch(`${base}/api/admin/withdrawal-requests?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getHistory(
  token: string,
  page = 1,
  outcome?: "APPROVED" | "REJECTED",
  q?: string,
): Promise<AdminWithdrawalHistoryResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  if (outcome) params.set("outcome", outcome);
  if (q) params.set("q", q);
  const res = await fetch(`${base}/api/admin/withdrawal-requests/history?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function approve(token: string, id: string): Promise<AdminWithdrawalApproveResponse> {
  const res = await fetch(`${base}/api/admin/withdrawal-requests/${id}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reject(token: string, id: string, reason: string): Promise<AdminWithdrawalRejectResponse> {
  const res = await fetch(`${base}/api/admin/withdrawal-requests/${id}/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
