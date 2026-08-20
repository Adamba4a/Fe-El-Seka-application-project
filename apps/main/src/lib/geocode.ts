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

// The public Nominatim instance has no SLA and can occasionally stall for a
// long time with no response — without a timeout, a slow request just hangs
// the pin-drop flow indefinitely with no feedback. Bound every call so it
// always resolves (falling back to raw coordinates / no bbox) within a few
// seconds.
const GEOCODE_TIMEOUT_MS = 6000;

function fetchWithTimeout(url: string, timeoutMs = GEOCODE_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { headers: { "Accept-Language": "en" }, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

interface NominatimResult {
  lat: string;
  lon: string;
  display_name: string;
  boundingbox?: [string, string, string, string]; // [south, north, west, east]
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

// Greater Cairo bounding box (west, north, east, south)
const CAIRO_VIEWBOX = "30.7,30.5,32.2,29.7";

function toSearchLocation(r: NominatimResult): SearchLocation {
  return { lat: parseFloat(r.lat), lng: parseFloat(r.lon), address: r.display_name, bbox: toBbox(r.boundingbox) };
}

// Reverse-geocodes a map pin to the bounding box of its enclosing city/district
// (zoom=10 ≈ city level), not the pin's own precise address. Used so a
// destination picked by dropping a pin still benefits from the same
// area-level dropoff matching that typing a district name gives — a driver
// whose route ends anywhere inside that area counts as a valid dropoff even
// if the exact drop point is a few km from the pin (see route_service's
// driver_dest_in_bbox check).
export async function reverseGeocodeAreaBbox(lat: number, lng: number): Promise<SearchBbox | null> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lng),
    format: "json",
    zoom: "10",
  });
  try {
    const res = await fetchWithTimeout(`https://nominatim.openstreetmap.org/reverse?${params}`);
    if (!res.ok) return null;
    const result: NominatimResult = await res.json();
    return toBbox(result.boundingbox);
  } catch {
    return null;
  }
}

export async function geocodeAddress(query: string): Promise<SearchLocation | null> {
  const params = new URLSearchParams({
    format: "json",
    q: query,
    limit: "1",
    countrycodes: "eg",
    viewbox: CAIRO_VIEWBOX,
    bounded: "1",
  });
  try {
    const res = await fetchWithTimeout(`https://nominatim.openstreetmap.org/search?${params}`);
    if (!res.ok) return null;
    const results: NominatimResult[] = await res.json();
    // If bounded search found nothing, retry without the viewbox constraint
    if (!results.length) {
      const fallback = new URLSearchParams({ format: "json", q: query, limit: "1", countrycodes: "eg" });
      const res2 = await fetchWithTimeout(`https://nominatim.openstreetmap.org/search?${fallback}`);
      if (!res2.ok) return null;
      const results2: NominatimResult[] = await res2.json();
      if (!results2.length) return null;
      return toSearchLocation(results2[0]);
    }
    return toSearchLocation(results[0]);
  } catch {
    return null;
  }
}
