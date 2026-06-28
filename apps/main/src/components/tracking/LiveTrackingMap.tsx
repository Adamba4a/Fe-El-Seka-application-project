"use client";

import { useEffect, useRef } from "react";
import type { DriverLocationData } from "../../lib/api/location";

interface LiveTrackingMapProps {
  location: DriverLocationData | null;
  isStale: boolean;
}

const CAIRO_CENTER: [number, number] = [30.0444, 31.2357];

export function LiveTrackingMap({ location, isStale }: LiveTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const markerRef = useRef<import("leaflet").Marker | null>(null);
  const centeredRef = useRef(false);

  // Initialize map once on mount
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let mounted = true;

    import("leaflet").then((leaflet) => {
      if (!mounted || !containerRef.current) return;
      const L = leaflet.default ?? leaflet;

      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const map = L.map(containerRef.current!).setView(CAIRO_CENTER, 14);
      mapRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);
    });

    return () => {
      mounted = false;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerRef.current = null;
        centeredRef.current = false;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update marker position whenever location changes
  useEffect(() => {
    if (!location || !mapRef.current) return;

    import("leaflet").then((leaflet) => {
      const L = leaflet.default ?? leaflet;
      const map = mapRef.current;
      if (!map) return;

      const latlng: [number, number] = [location.lat, location.lng];

      if (markerRef.current) {
        markerRef.current.setLatLng(latlng);
      } else {
        const icon =
          location.bearing != null
            ? L.divIcon({
                className: "",
                html: `<div style="transform:rotate(${location.bearing}deg);font-size:24px;line-height:1;">🚗</div>`,
                iconAnchor: [12, 12],
              })
            : new L.Icon.Default();

        markerRef.current = L.marker(latlng, { icon }).addTo(map);
      }

      // Update bearing rotation on existing marker icon
      if (location.bearing != null && markerRef.current) {
        const el = markerRef.current.getElement();
        if (el) {
          const inner = el.querySelector("div") as HTMLElement | null;
          if (inner) inner.style.transform = `rotate(${location.bearing}deg)`;
        }
      }

      // Center map only on first position
      if (!centeredRef.current) {
        map.setView(latlng, 15);
        centeredRef.current = true;
      }
    });
  }, [location]);

  return (
    <div
      ref={containerRef}
      className={`w-full h-full rounded-xl z-0 ${isStale ? "opacity-75" : ""}`}
    />
  );
}
