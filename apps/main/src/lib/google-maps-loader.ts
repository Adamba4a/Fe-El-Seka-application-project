import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import { env } from "./env";

let loaderPromise: Promise<typeof google> | null = null;

// The "maps" library covers Map/Polyline/InfoWindow/OverlayView/etc, "marker"
// covers the classic Marker class, "places" covers Autocomplete.
const LIBRARIES = ["maps", "marker", "places"] as const;

export function loadGoogleMaps(): Promise<typeof google> {
  if (!loaderPromise) {
    if (!env.googleMapsApiKey) {
      loaderPromise = Promise.reject(new Error("Missing NEXT_PUBLIC_GOOGLE_MAPS_API_KEY"));
    } else {
      setOptions({ key: env.googleMapsApiKey, v: "weekly" });
      loaderPromise = Promise.all(LIBRARIES.map((library) => importLibrary(library))).then(() => google);
    }
  }
  return loaderPromise;
}
