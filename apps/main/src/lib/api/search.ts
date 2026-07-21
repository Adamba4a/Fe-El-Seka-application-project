import { env } from "../env";

export interface RideCandidate {
  ride_id: string;
  driver: {
    display_name: string | null;
    avatar_url: string | null;
    is_verified: boolean;
  };
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  candidate_type: "standard" | "premium";
  match_score_pct: number | null;
  compatibility: {
    overlap_percentage: number;
    pickup_walk_meters: number;
    dropoff_walk_meters: number;
    driver_detour_km: number;
    driver_detour_minutes: number;
    is_compatible: boolean;
    premium_pickup_available: boolean;
    premium_pickup_fee: number | null;
    premium_dropoff_available: boolean;
    premium_dropoff_fee: number | null;
  };
}

export interface RideSearchResponse {
  candidates: RideCandidate[];
  total: number;
  no_rides_found: boolean;
  ai_ranking_active: boolean;
}

export interface NearbyRide {
  ride_id: string;
  driver: {
    display_name: string | null;
    avatar_url: string | null;
    is_verified: boolean;
  };
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  origin_address: string;
  destination_address: string;
  destination_lat: number;
  destination_lng: number;
  distance_meters: number;
}

export async function getNearbyRides(
  token: string,
  lat: number,
  lng: number,
  limit = 2
): Promise<NearbyRide[]> {
  const query = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
    limit: String(limit),
  });
  const res = await fetch(`${env.apiUrl}/api/v1/search/nearby?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json.rides;
}

export async function searchRides(
  token: string,
  params: {
    origin: { lat: number; lng: number };
    destination: { lat: number; lng: number };
    dest_bbox?: { south: number; north: number; west: number; east: number } | null;
    desired_departure_at?: string;
  }
): Promise<RideSearchResponse> {
  const res = await fetch(`${env.apiUrl}/api/v1/search/rides`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
