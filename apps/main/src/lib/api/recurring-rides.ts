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

// The backend stores `departure_time` as a UTC time-of-day, combined with each
// instance's calendar date at generation time (no per-driver timezone on the
// definition). The driver picks a time in their own browser's local timezone,
// so we convert local HH:MM <-> UTC HH:MM here rather than in the backend.
export function localTimeToUtcTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const now = new Date();
  const local = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);
  return `${String(local.getUTCHours()).padStart(2, "0")}:${String(local.getUTCMinutes()).padStart(2, "0")}`;
}

export function utcTimeToLocalTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const now = new Date();
  const utc = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0));
  return `${String(utc.getHours()).padStart(2, "0")}:${String(utc.getMinutes()).padStart(2, "0")}`;
}

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

export interface RecurringInstanceOption {
  ride_id: string;
  departure_datetime: string;
  available_seats: number;
  total_seats: number;
  per_seat_price: string;
  existing_booking: { booking_id: string; status: string; seats: number } | null;
}

export interface RecurringInstancesResponse {
  instances: RecurringInstanceOption[];
}

export async function listRecurringInstancesForRide(
  token: string,
  rideId: string
): Promise<RecurringInstancesResponse> {
  const res = await fetch(`${base}/api/v1/rides/${rideId}/recurring-instances`, {
    headers: { Authorization: `Bearer ${token}` },
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
