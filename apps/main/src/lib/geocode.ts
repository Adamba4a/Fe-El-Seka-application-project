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

// Greater Cairo bounding box (west, north, east, south)
const CAIRO_VIEWBOX = "30.7,30.5,32.2,29.7";

function toSearchLocation(r: NominatimResult): SearchLocation {
  const bbox: SearchBbox | null = r.boundingbox
    ? {
        south: parseFloat(r.boundingbox[0]),
        north: parseFloat(r.boundingbox[1]),
        west: parseFloat(r.boundingbox[2]),
        east: parseFloat(r.boundingbox[3]),
      }
    : null;
  return { lat: parseFloat(r.lat), lng: parseFloat(r.lon), address: r.display_name, bbox };
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
