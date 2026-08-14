const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface AdminTopupQueueItem {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string;
  amount_egp: string;
  payment_reference: string;
  screenshot_url: string;
  created_at: string;
}

export interface AdminTopupQueueResponse {
  total: number;
  page: number;
  items: AdminTopupQueueItem[];
}

export interface AdminTopupHistoryItem {
  request_id: string;
  driver_id: string;
  driver_name: string;
  amount_egp: string;
  status: "APPROVED" | "REJECTED";
  rejection_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  driver_is_locked: boolean;
}

export interface AdminTopupHistoryResponse {
  total: number;
  page: number;
  items: AdminTopupHistoryItem[];
}

export interface AdminTopupApproveResponse {
  id: string;
  status: string;
  ledger_entry_id: string;
  new_balance_egp: string;
  reviewed_by: string;
  reviewed_at: string;
}

export interface AdminTopupRejectResponse {
  id: string;
  status: string;
  rejection_reason: string;
  reviewed_by: string;
  reviewed_at: string;
  driver_locked: boolean;
}

export interface AdminTopupUnlockResponse {
  driver_id: string;
  is_topup_locked: boolean;
}

export async function getQueue(token: string, page = 1): Promise<AdminTopupQueueResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  const res = await fetch(`${base}/api/admin/wallet-topup-requests?${params}`, {
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
): Promise<AdminTopupHistoryResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  if (outcome) params.set("outcome", outcome);
  if (q) params.set("q", q);
  const res = await fetch(`${base}/api/admin/wallet-topup-requests/history?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function approve(token: string, id: string): Promise<AdminTopupApproveResponse> {
  const res = await fetch(`${base}/api/admin/wallet-topup-requests/${id}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reject(token: string, id: string, reason: string): Promise<AdminTopupRejectResponse> {
  const res = await fetch(`${base}/api/admin/wallet-topup-requests/${id}/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function unlock(token: string, driverId: string): Promise<AdminTopupUnlockResponse> {
  const res = await fetch(`${base}/api/admin/wallet-topup-requests/drivers/${driverId}/unlock`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
