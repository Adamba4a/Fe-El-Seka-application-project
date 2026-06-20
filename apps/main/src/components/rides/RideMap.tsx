"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Coordinates } from "@fe-el-seka/shared";

interface RideMapProps {
  label: string;
  initialCoordinates?: Coordinates;
  onPinDrop: (coords: Coordinates, address: string) => void;
}

const NOMINATIM_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_NOMINATIM_URL ?? "https://nominatim.openstreetmap.org")
    : "https://nominatim.openstreetmap.org";

const CAIRO_CENTER: [number, number] = [30.0444, 31.2357];

export function RideMap({ label, initialCoordinates, onPinDrop }: RideMapProps) {
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const markerRef = useRef<import("leaflet").Marker | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [address, setAddress] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const reverseGeocode = useCallback(
    async (lat: number, lng: number) => {
      setLoading(true);
      try {
        const res = await fetch(
          `${NOMINATIM_URL}/reverse?lat=${lat}&lon=${lng}&format=json`,
          { headers: { "Accept-Language": "en" } }
        );
        if (!res.ok) throw new Error("Nominatim error");
        const data = await res.json();
        const label = data.display_name ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        setAddress(label);
        onPinDrop({ lat, lng }, label);
      } catch {
        const fallback = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        setAddress(fallback);
        onPinDrop({ lat, lng }, fallback);
      } finally {
        setLoading(false);
      }
    },
    [onPinDrop]
  );

  const handleMapClick = useCallback(
    (lat: number, lng: number, L: typeof import("leaflet"), map: import("leaflet").Map) => {
      if (markerRef.current) {
        markerRef.current.setLatLng([lat, lng]);
      } else {
        markerRef.current = L.marker([lat, lng]).addTo(map);
      }

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => reverseGeocode(lat, lng), 300);
    },
    [reverseGeocode]
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let L: typeof import("leaflet");
    let mounted = true;

    import("leaflet").then((leaflet) => {
      if (!mounted || !containerRef.current) return;
      L = leaflet.default ?? leaflet;

      // Fix default icon paths broken by webpack bundling
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const center: [number, number] = initialCoordinates
        ? [initialCoordinates.lat, initialCoordinates.lng]
        : CAIRO_CENTER;

      const map = L.map(containerRef.current!).setView(center, 12);
      mapRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      if (initialCoordinates) {
        markerRef.current = L.marker([initialCoordinates.lat, initialCoordinates.lng]).addTo(map);
      }

      map.on("click", (e: import("leaflet").LeafletMouseEvent) => {
        handleMapClick(e.latlng.lat, e.latlng.lng, L, map);
      });
    });

    return () => {
      mounted = false;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2">
      <label className="block text-label text-content-secondary">{label}</label>
      <div ref={containerRef} className="w-full h-48 rounded-xl border border-border-default z-0" />
      {loading && <p className="text-caption text-content-muted">Getting address…</p>}
      {address && !loading && (
        <p className="text-caption text-content-secondary truncate" title={address}>
          📍 {address}
        </p>
      )}
    </div>
  );
}
