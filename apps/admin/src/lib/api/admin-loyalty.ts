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

export interface AdminLoyaltyCatalogEntry {
  id: string;
  type: string;
  title: string;
  description: string;
  audience: "passenger" | "driver" | "both";
  point_cost: number;
  fulfillment_mode: "instant" | "manual";
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminLoyaltyCatalogListResponse {
  items: AdminLoyaltyCatalogEntry[];
}

export interface AdminLoyaltyCatalogCreateInput {
  title: string;
  description: string;
  audience: "passenger" | "driver" | "both";
  point_cost: number;
  fulfillment_mode: "instant" | "manual";
}

export interface AdminLoyaltyCatalogUpdateInput {
  title?: string;
  description?: string;
  point_cost?: number;
  fulfillment_mode?: "instant" | "manual";
  active?: boolean;
  loyalty_free_ride_max_fare_egp?: string;
  loyalty_discount_percentage?: number;
}

export async function getCatalog(token: string): Promise<AdminLoyaltyCatalogListResponse> {
  const res = await fetch(`${base}/api/admin/loyalty/catalog`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function createVoucher(
  token: string,
  input: AdminLoyaltyCatalogCreateInput
): Promise<AdminLoyaltyCatalogEntry> {
  const res = await fetch(`${base}/api/admin/loyalty/catalog`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function updateCatalogEntry(
  token: string,
  id: string,
  input: AdminLoyaltyCatalogUpdateInput
): Promise<AdminLoyaltyCatalogEntry> {
  const res = await fetch(`${base}/api/admin/loyalty/catalog/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function retireCatalogEntry(token: string, id: string): Promise<AdminLoyaltyCatalogEntry> {
  const res = await fetch(`${base}/api/admin/loyalty/catalog/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
