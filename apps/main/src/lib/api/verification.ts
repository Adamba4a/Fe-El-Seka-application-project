import type { VerificationSubmission, VerificationStatus } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

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
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getStatus(token: string): Promise<VerificationStatus> {
  const res = await fetch(`${base}/api/verification/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
