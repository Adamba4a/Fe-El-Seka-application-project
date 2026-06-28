import { env } from "../env";

const base = env.apiUrl;

export interface RegisterDeviceTokenPayload {
  token: string;
  platform: "web" | "android" | "ios";
}

export interface DeviceTokenResponse {
  token_id: string;
  user_id: string;
  platform: string;
  last_seen_at: string;
}

export async function registerDeviceToken(
  token: string,
  data: RegisterDeviceTokenPayload
): Promise<DeviceTokenResponse> {
  const res = await fetch(`${base}/api/v1/users/me/device-tokens`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
