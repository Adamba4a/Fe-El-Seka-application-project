import type {
  OrgAccessConfirmBody,
  OrgAccessConfirmResponse,
  OrgAccessRequestBody,
  OrgAccessRequestResponse,
} from "@fe-el-seka/shared";

import { env } from "../env";

const base = env.apiUrl;

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key ({"detail": {"error": ..., "message": ...}}) — unwrap it so
// callers can check err.error / err.message directly.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return { message: res.statusText || `Request failed with status ${res.status}` };
  }
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "object") {
    return body.detail as { error?: string; message?: string };
  }
  return body as { error?: string; message?: string };
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function requestOrgAccessVerification(
  token: string,
  payload: OrgAccessRequestBody
): Promise<OrgAccessRequestResponse> {
  const res = await fetch(`${base}/api/v1/org-access/request`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function confirmOrgAccessVerification(
  token: string,
  payload: OrgAccessConfirmBody
): Promise<OrgAccessConfirmResponse> {
  const res = await fetch(`${base}/api/v1/org-access/confirm`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}
