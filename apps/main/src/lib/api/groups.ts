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
