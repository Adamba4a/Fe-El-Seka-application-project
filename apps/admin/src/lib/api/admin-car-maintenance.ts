const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface AdminCarMaintenanceQueueItem {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string;
  amount_egp: string;
  reached_at: string;
}

export interface AdminCarMaintenanceQueueResponse {
  total: number;
  page: number;
  items: AdminCarMaintenanceQueueItem[];
}

export interface AdminCarMaintenanceFulfillResponse {
  id: string;
  status: string;
  fulfilled_by: string;
  fulfilled_at: string;
}

export async function getQueue(token: string, page = 1): Promise<AdminCarMaintenanceQueueResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  const res = await fetch(`${base}/api/admin/car-maintenance-rewards?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function fulfill(token: string, id: string): Promise<AdminCarMaintenanceFulfillResponse> {
  const res = await fetch(`${base}/api/admin/car-maintenance-rewards/${id}/fulfill`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
