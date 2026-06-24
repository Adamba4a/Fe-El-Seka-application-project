"use client";

import { useEffect, useRef } from "react";

export interface LatLng {
  lat: number;
  lng: number;
}

interface RideDetailMapProps {
  routeGeometry: object | null;   // GeoJSON LineString from the API
  boardingPoint: LatLng | null;
  alightingPoint: LatLng | null;
  origin: LatLng;
  destination: LatLng;
}

export function RideDetailMap({
  routeGeometry,
  boardingPoint,
  alightingPoint,
  origin,
  destination,
}: RideDetailMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let mounted = true;

    import("leaflet").then((leaflet) => {
      if (!mounted || !containerRef.current || mapRef.current) return;
      const L = leaflet.default ?? leaflet;

      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      // Centre on boarding point or origin as fallback
      const center = boardingPoint ?? origin;
      const map = L.map(containerRef.current!).setView([center.lat, center.lng], 13);
      mapRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      // Blue driver route polyline
      if (routeGeometry) {
        L.geoJSON(routeGeometry as GeoJSON.LineString, {
          style: { color: "#2563eb", weight: 4, opacity: 0.85 },
        }).addTo(map);
      }

      // Walk line: origin → boarding (dashed grey)
      if (boardingPoint) {
        L.polyline([[origin.lat, origin.lng], [boardingPoint.lat, boardingPoint.lng]], {
          color: "#9ca3af",
          weight: 2,
          dashArray: "6 4",
          opacity: 0.8,
        }).addTo(map);

        // Green boarding pin
        const greenIcon = L.divIcon({
          className: "",
          html: '<div style="width:14px;height:14px;border-radius:50%;background:#16a34a;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)"></div>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        L.marker([boardingPoint.lat, boardingPoint.lng], { icon: greenIcon })
          .bindTooltip("Boarding", { permanent: false })
          .addTo(map);
      }

      // Walk line: alighting → destination (dashed grey)
      if (alightingPoint) {
        L.polyline([[alightingPoint.lat, alightingPoint.lng], [destination.lat, destination.lng]], {
          color: "#9ca3af",
          weight: 2,
          dashArray: "6 4",
          opacity: 0.8,
        }).addTo(map);

        // Red alighting pin
        const redIcon = L.divIcon({
          className: "",
          html: '<div style="width:14px;height:14px;border-radius:50%;background:#dc2626;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)"></div>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        L.marker([alightingPoint.lat, alightingPoint.lng], { icon: redIcon })
          .bindTooltip("Alighting", { permanent: false })
          .addTo(map);
      }

      // Fit bounds to show everything
      const points: [number, number][] = [
        [origin.lat, origin.lng],
        [destination.lat, destination.lng],
      ];
      if (boardingPoint) points.push([boardingPoint.lat, boardingPoint.lng]);
      if (alightingPoint) points.push([alightingPoint.lat, alightingPoint.lng]);
      map.fitBounds(L.latLngBounds(points), { padding: [24, 24] });
    });

    return () => {
      mounted = false;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={containerRef} className="w-full h-56 rounded-xl border border-border-default z-0" />
  );
}
