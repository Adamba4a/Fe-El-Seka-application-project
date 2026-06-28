import { env } from "../env";

const base = env.apiUrl;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface LocationUpdatePayload {
  lat: number;
  lng: number;
  bearing?: number | null;
  speed_kmh?: number | null;
  client_timestamp: string;
}

export interface DriverLocationData {
  lat: number;
  lng: number;
  bearing: number | null;
  updatedAt: string;
}

export async function reportLocation(
  token: string,
  rideId: string,
  data: LocationUpdatePayload
): Promise<void> {
  const res = await fetch(`${base}/api/v1/rides/${rideId}/location`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw json;
}

export async function getDriverLocation(
  token: string,
  rideId: string
): Promise<DriverLocationData | null> {
  const res = await fetch(`${base}/api/v1/rides/${rideId}/location`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 404) return null;
  const json = await res.json();
  if (!res.ok) throw json;
  return {
    lat: json.lat,
    lng: json.lng,
    bearing: json.bearing ?? null,
    updatedAt: json.updated_at,
  };
}
