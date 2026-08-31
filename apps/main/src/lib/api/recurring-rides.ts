import type {
  RecurringRideDefinition,
  CreateRecurringRideDefinitionPayload,
  EditRecurringRideDefinitionPayload,
  RecurringRideDefinitionListResponse,
  RecurringRideDefinitionDetailResponse,
  RecurringRideDefinitionUpdateResponse,
} from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key — unwrap it so callers can check err.error / err.message directly.
function unwrapError(body: unknown): { error?: string; message?: string } {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (detail && typeof detail === "object") return detail;
  }
  return (body ?? {}) as { error?: string; message?: string };
}

export async function createRecurringDefinition(
  token: string,
  data: CreateRecurringRideDefinitionPayload
): Promise<RecurringRideDefinition> {
  const res = await fetch(`${base}/api/v1/rides/recurring`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw unwrapError(json);
  return json;
}

export async function listRecurringDefinitions(
  token: string
): Promise<RecurringRideDefinitionListResponse> {
  const res = await fetch(`${base}/api/v1/rides/recurring`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw unwrapError(json);
  return json;
}

export async function getRecurringDefinition(
  token: string,
  id: string
): Promise<RecurringRideDefinitionDetailResponse> {
  const res = await fetch(`${base}/api/v1/rides/recurring/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw unwrapError(json);
  return json;
}

export async function editRecurringDefinition(
  token: string,
  id: string,
  data: EditRecurringRideDefinitionPayload
): Promise<RecurringRideDefinitionUpdateResponse> {
  const res = await fetch(`${base}/api/v1/rides/recurring/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw unwrapError(json);
  return json;
}

export async function endRecurringDefinition(
  token: string,
  id: string
): Promise<RecurringRideDefinition> {
  const res = await fetch(`${base}/api/v1/rides/recurring/${id}/end`, {
    method: "POST",
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw unwrapError(json);
  return json;
}
