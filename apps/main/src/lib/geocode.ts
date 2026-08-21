import { env } from "./env";
import { createClient } from "./supabase/client";

export interface SearchBbox {
  south: number;
  north: number;
  west: number;
  east: number;
}

export interface SearchLocation {
  lat: number;
  lng: number;
  address: string;
  bbox?: SearchBbox | null;
}

// Calls go through our own backend (/api/geocode/*), not directly to
// Nominatim. Nominatim's usage policy requires an identifying User-Agent and
// throttles requests without one — calling it straight from the browser (and
// especially from mobile carriers, which share a handful of NAT'd IPs across
// many users) tripped that throttling constantly, which is what made pin
// drops stall for the full timeout and fall back to raw coordinates. The
// backend proxy sends a proper User-Agent and caches repeat lookups.
const GEOCODE_TIMEOUT_MS = 6000;

function fetchWithTimeout(url: string, headers: HeadersInit, timeoutMs = GEOCODE_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { headers, signal: controller.signal }).finally(() => clearTimeout(timer));
}

async function authHeaders(): Promise<HeadersInit> {
  const { data: { session } } = await createClient().auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

interface ReverseGeocodeResult {
  address: string | null;
  boundingbox?: [string, string, string, string]; // [south, north, west, east]
}

interface SearchResult {
  lat: string;
  lon: string;
  display_name: string;
  boundingbox?: [string, string, string, string];
}

function toBbox(boundingbox?: [string, string, string, string]): SearchBbox | null {
  if (!boundingbox) return null;
  return {
    south: parseFloat(boundingbox[0]),
    north: parseFloat(boundingbox[1]),
    west: parseFloat(boundingbox[2]),
    east: parseFloat(boundingbox[3]),
  };
}

// Reverse-geocodes a map pin to its human-readable address.
export async function reverseGeocodeAddress(lat: number, lng: number): Promise<string | null> {
  try {
    const params = new URLSearchParams({ lat: String(lat), lng: String(lng) });
    const res = await fetchWithTimeout(`${env.apiUrl}/api/geocode/reverse?${params}`, await authHeaders());
    if (!res.ok) return null;
    const result: ReverseGeocodeResult = await res.json();
    return result.address ?? null;
  } catch {
    return null;
  }
}

// Reverse-geocodes a map pin to the bounding box of its enclosing city/district
// (zoom=10 ≈ city level), not the pin's own precise address. Used so a
// destination picked by dropping a pin still benefits from the same
// area-level dropoff matching that typing a district name gives — a driver
// whose route ends anywhere inside that area counts as a valid dropoff even
// if the exact drop point is a few km from the pin (see route_service's
// driver_dest_in_bbox check).
export async function reverseGeocodeAreaBbox(lat: number, lng: number): Promise<SearchBbox | null> {
  try {
    const params = new URLSearchParams({ lat: String(lat), lng: String(lng) });
    const res = await fetchWithTimeout(`${env.apiUrl}/api/geocode/reverse?${params}`, await authHeaders());
    if (!res.ok) return null;
    const result: ReverseGeocodeResult = await res.json();
    return toBbox(result.boundingbox);
  } catch {
    return null;
  }
}

export async function geocodeAddress(query: string): Promise<SearchLocation | null> {
  try {
    const params = new URLSearchParams({ q: query });
    const res = await fetchWithTimeout(`${env.apiUrl}/api/geocode/search?${params}`, await authHeaders());
    if (!res.ok) return null;
    const result: SearchResult = await res.json();
    return {
      lat: parseFloat(result.lat),
      lng: parseFloat(result.lon),
      address: result.display_name,
      bbox: toBbox(result.boundingbox),
    };
  } catch {
    return null;
  }
}
