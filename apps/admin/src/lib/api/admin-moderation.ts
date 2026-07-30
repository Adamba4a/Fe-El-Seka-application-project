const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface ReportParty {
  user_id: string;
  display_name: string;
}

export interface QueueReport {
  report_id: string;
  category: string;
  description: string;
  reporter: ReportParty;
  reported_user: ReportParty;
  ride_id: string;
  status: "open" | "under_review";
  created_at: string;
}

export interface QueueResponse {
  items: QueueReport[];
  total: number;
  page: number;
  limit: number;
}

export interface FlaggedUser {
  user_id: string;
  display_name: string;
  reason: "low_rating" | "report_count";
  rating_avg: number | null;
  recent_report_count: number | null;
}

export interface FlaggedResponse {
  items: FlaggedUser[];
}

export async function getQueue(token: string, page = 1): Promise<QueueResponse> {
  const res = await fetch(`${base}/api/admin/moderation/queue?page=${page}&limit=20`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getFlagged(token: string): Promise<FlaggedResponse> {
  const res = await fetch(`${base}/api/admin/moderation/flagged`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reviewReport(token: string, reportId: string): Promise<{ report_id: string; status: string }> {
  const res = await fetch(`${base}/api/admin/moderation/reports/${reportId}/review`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function resolveReport(
  token: string,
  reportId: string,
  action: "warn" | "suspend" | "dismiss",
  reason: string
): Promise<{ report_id: string; status: string; action: string; audit_log_id: string | null }> {
  const res = await fetch(`${base}/api/admin/moderation/reports/${reportId}/resolve`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ action, reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reinstateUser(
  token: string,
  userId: string,
  reason: string
): Promise<{ user_id: string; new_status: string; audit_log_id: string }> {
  const res = await fetch(`${base}/api/admin/moderation/users/${userId}/reinstate`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
