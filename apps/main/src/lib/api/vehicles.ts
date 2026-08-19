import type { Vehicle, VehicleRegistration, VehicleStructuralUpdate, VehicleUpdate, VehicleUpdateRequestRecord } from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

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

export async function registerVehicle(token: string, data: VehicleRegistration): Promise<Vehicle> {
  const res = await fetch(`${base}/api/vehicles/register`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getMyVehicle(token: string): Promise<Vehicle> {
  const res = await fetch(`${base}/api/vehicles/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function updateMyVehicle(token: string, data: VehicleUpdate): Promise<Vehicle> {
  const res = await fetch(`${base}/api/vehicles/me`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function requestVehicleUpdate(token: string, data: VehicleStructuralUpdate): Promise<VehicleUpdateRequestRecord> {
  const res = await fetch(`${base}/api/vehicles/me/update-request`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getPendingVehicleUpdate(token: string): Promise<VehicleUpdateRequestRecord | null> {
  const res = await fetch(`${base}/api/vehicles/me/update-request`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}
