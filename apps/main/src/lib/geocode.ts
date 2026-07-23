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
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?${params}`, {
      headers: { "Accept-Language": "en" },
    });
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
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
    headers: { "Accept-Language": "en" },
  });
  if (!res.ok) return null;
  const results: NominatimResult[] = await res.json();
  // If bounded search found nothing, retry without the viewbox constraint
  if (!results.length) {
    const fallback = new URLSearchParams({ format: "json", q: query, limit: "1", countrycodes: "eg" });
    const res2 = await fetch(`https://nominatim.openstreetmap.org/search?${fallback}`, {
      headers: { "Accept-Language": "en" },
    });
    if (!res2.ok) return null;
    const results2: NominatimResult[] = await res2.json();
    if (!results2.length) return null;
    return toSearchLocation(results2[0]);
  }
  return toSearchLocation(results[0]);
}
