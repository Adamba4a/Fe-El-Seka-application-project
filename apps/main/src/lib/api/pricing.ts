import { env } from "../env";
import type { Coordinates } from "@fe-el-seka/shared";

const base = env.apiUrl;

export interface FareEstimate {
  per_seat_price_egp: number;
  max_price_per_seat_egp: number;
}

export async function getFareEstimate(
  origin: Coordinates,
  destination: Coordinates,
  seatCount: number
): Promise<FareEstimate> {
  const res = await fetch(`${base}/api/routes/fare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin: { lat: origin.lat, lng: origin.lng },
      destination: { lat: destination.lat, lng: destination.lng },
      seat_count: seatCount,
    }),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return {
    per_seat_price_egp: json.per_seat_price_egp,
    max_price_per_seat_egp: json.max_price_per_seat_egp,
  };
}
