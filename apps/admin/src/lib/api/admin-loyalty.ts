const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface AdminLoyaltyQueueItem {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  role: "passenger" | "driver";
  catalog_entry: { type: string; title: string };
  points_spent: number;
  created_at: string;
}

export interface AdminLoyaltyQueueResponse {
  total: number;
  page: number;
  items: AdminLoyaltyQueueItem[];
}

export interface AdminLoyaltyQueueActionResponse {
  id: string;
  status: string;
  fulfilled_by: string | null;
  fulfilled_at: string | null;
}

export async function getQueue(token: string, page = 1): Promise<AdminLoyaltyQueueResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  const res = await fetch(`${base}/api/admin/loyalty/queue?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function fulfill(token: string, id: string): Promise<AdminLoyaltyQueueActionResponse> {
  const res = await fetch(`${base}/api/admin/loyalty/queue/${id}/fulfill`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reject(
  token: string,
  id: string,
  reason: string
): Promise<AdminLoyaltyQueueActionResponse> {
  const res = await fetch(`${base}/api/admin/loyalty/queue/${id}/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
