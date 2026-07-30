import type { AdminQueueResponse, AdminSubmissionDetail } from "@fe-el-seka/shared";

const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function getQueue(token: string, type?: string, page = 1): Promise<AdminQueueResponse> {
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  if (type) params.set("type", type);
  const res = await fetch(`${base}/api/admin/verification/queue?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getSubmission(token: string, id: string): Promise<AdminSubmissionDetail> {
  const res = await fetch(`${base}/api/admin/verification/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function approve(token: string, id: string): Promise<{ new_status: string; audit_log_id: string }> {
  const res = await fetch(`${base}/api/admin/verification/${id}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reject(token: string, id: string, reason: string): Promise<{ new_status: string; is_locked: boolean }> {
  const res = await fetch(`${base}/api/admin/verification/${id}/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function unlock(token: string, userId: string): Promise<{ is_submission_locked: boolean }> {
  const res = await fetch(`${base}/api/admin/verification/users/${userId}/unlock`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getHistory(token: string, page = 1): Promise<{ total: number; items: unknown[] }> {
  const res = await fetch(`${base}/api/admin/verification/history?page=${page}&limit=20`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
