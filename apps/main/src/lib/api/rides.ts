import type {
  Ride,
  CreateRidePayload,
  EditRidePayload,
  CancelRidePayload,
  RideListResponse,
  RideDetailResponse,
} from "@fe-el-seka/shared";
import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function createRide(token: string, data: CreateRidePayload): Promise<Ride> {
  const res = await fetch(`${base}/api/v1/rides`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.ride;
}

export async function listRides(
  token: string,
  params: { status?: string; page?: number; page_size?: number } = {}
): Promise<RideListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));

  const res = await fetch(`${base}/api/v1/rides?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function getRide(token: string, id: string): Promise<RideDetailResponse> {
  const res = await fetch(`${base}/api/v1/rides/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function editRide(token: string, id: string, data: EditRidePayload): Promise<Ride> {
  const res = await fetch(`${base}/api/v1/rides/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.ride;
}

export async function cancelRide(token: string, id: string, data: CancelRidePayload): Promise<Ride> {
  const res = await fetch(`${base}/api/v1/rides/${id}/cancel`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.ride;
}

export async function startRide(token: string, id: string): Promise<Ride> {
  const res = await fetch(`${base}/api/v1/rides/${id}/start`, {
    method: "POST",
    headers: authHeaders(token),
    body: "{}",
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.ride;
}

export async function completeRide(token: string, id: string): Promise<Ride> {
  const res = await fetch(`${base}/api/v1/rides/${id}/complete`, {
    method: "POST",
    headers: authHeaders(token),
    body: "{}",
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.ride;
}
