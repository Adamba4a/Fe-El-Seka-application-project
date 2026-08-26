import { env } from "../env";

const base = env.apiUrl;

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key ({"detail": {"error": ..., "message": ...}}) — unwrap it so
// callers can check err.error / err.message directly.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  const body = await res.json();
  if (body && typeof body === "object" && body.detail && typeof body.detail === "object") {
    return body.detail;
  }
  return body;
}
