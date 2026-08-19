import type { VerificationSubmission, VerificationStatus } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key ({"detail": {"error": ..., "message": ...}}) — unwrap it so
// callers can check err.error / err.message directly.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string; support_email?: string }> {
  const body = await res.json();
  if (body && typeof body === "object" && body.detail && typeof body.detail === "object") {
    return body.detail;
  }
  return body;
}

export async function submitDocuments(
  token: string,
  frontId: File,
  backId: File,
  license?: File
): Promise<VerificationSubmission> {
  const form = new FormData();
  form.append("front_id", frontId);
  form.append("back_id", backId);
  if (license) form.append("license", license);

  const res = await fetch(`${base}/api/verification/submit`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getStatus(token: string): Promise<VerificationStatus> {
  const res = await fetch(`${base}/api/verification/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}
