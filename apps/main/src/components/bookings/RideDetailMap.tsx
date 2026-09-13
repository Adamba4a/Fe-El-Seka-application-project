"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { loadGoogleMaps } from "@/lib/google-maps-loader";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface PassengerPoint {
  id: string;
  label: string; // passenger display name, shown in the marker info window
  boardingPoint: LatLng;
  alightingPoint: LatLng;
}

interface RideDetailMapProps {
  routeGeometry: object | null;   // GeoJSON LineString from the API
  boardingPoint: LatLng | null;
  alightingPoint: LatLng | null;
  origin: LatLng;
  destination: LatLng;
  // When provided (non-empty), all passengers are plotted together instead of
  // the single boardingPoint/alightingPoint pair above — used by driver views
  // that need to see every booked passenger's pickup/dropoff on one map.
  passengers?: PassengerPoint[];
}

const PASSENGER_COLORS = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#9333ea",
  "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5",
];

interface GeoJsonLineString {
  type: "LineString";
  coordinates: [number, number][]; // [lng, lat]
}

// Fully transparent base line + a repeated line-symbol along it — Google's
// Polyline has no native dashArray, this is the standard workaround.
function dashedLineOptions(path: LatLng[]): google.maps.PolylineOptions {
  return {
    path,
    strokeColor: "#9ca3af",
    strokeOpacity: 0,
    icons: [
      {
        icon: { path: "M 0,-1 0,1", strokeOpacity: 0.8, strokeColor: "#9ca3af", scale: 3 },
        offset: "0",
        repeat: "10px",
      },
    ],
  };
}

function circlePinOptions(color: string): google.maps.Symbol {
  return {
    path: google.maps.SymbolPath.CIRCLE,
    scale: 7,
    fillColor: color,
    fillOpacity: 1,
    strokeColor: "#fff",
    strokeWeight: 2,
  };
}

function pinLabel(text: string): google.maps.MarkerLabel {
  return { text, color: "#fff", fontSize: "9px", fontWeight: "700" };
}

export function RideDetailMap({
  routeGeometry,
  boardingPoint,
  alightingPoint,
  origin,
  destination,
  passengers,
}: RideDetailMapProps) {
  const t = useTranslations("map");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const [mapError, setMapError] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let mounted = true;

    loadGoogleMaps()
      .then(() => {
        if (!mounted || !containerRef.current || mapRef.current) return;

        const center = boardingPoint ?? origin;
        const map = new google.maps.Map(containerRef.current, {
          center,
          zoom: 13,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        });
        mapRef.current = map;

        if (routeGeometry) {
          const geometry = routeGeometry as GeoJsonLineString;
          const path = geometry.coordinates.map(([lng, lat]) => ({ lat, lng }));
          new google.maps.Polyline({
            path,
            strokeColor: "#2563eb",
            strokeWeight: 4,
            strokeOpacity: 0.85,
            map,
          });
        }

        const bounds = new google.maps.LatLngBounds();
        bounds.extend(origin);
        bounds.extend(destination);

        const addPin = (position: LatLng, color: string, label: string, infoText: string) => {
          const marker = new google.maps.Marker({
            position,
            map,
            icon: circlePinOptions(color),
            label: pinLabel(label),
          });
          const info = new google.maps.InfoWindow({ content: infoText, disableAutoPan: true });
          marker.addListener("mouseover", () => info.open(map, marker));
          marker.addListener("mouseout", () => info.close());
          bounds.extend(position);
        };

        if (passengers && passengers.length > 0) {
          passengers.forEach((passenger, i) => {
            const color = PASSENGER_COLORS[i % PASSENGER_COLORS.length];

            new google.maps.Polyline({ ...dashedLineOptions([origin, passenger.boardingPoint]), map });
            addPin(passenger.boardingPoint, color, "B", `${passenger.label} — ${t("boarding")}`);

            new google.maps.Polyline({ ...dashedLineOptions([passenger.alightingPoint, destination]), map });
            addPin(passenger.alightingPoint, color, "D", `${passenger.label} — ${t("alighting")}`);
          });
        } else {
          if (boardingPoint) {
            new google.maps.Polyline({ ...dashedLineOptions([origin, boardingPoint]), map });
            addPin(boardingPoint, "#16a34a", "B", t("boarding"));
          }

          if (alightingPoint) {
            new google.maps.Polyline({ ...dashedLineOptions([alightingPoint, destination]), map });
            addPin(alightingPoint, "#dc2626", "D", t("alighting"));
          }
        }

        map.fitBounds(bounds, { top: 24, right: 24, bottom: 24, left: 24 });
      })
      .catch(() => {
        if (mounted) setMapError(true);
      });

    return () => {
      mounted = false;
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (mapError) {
    return (
      <div className="w-full h-56 rounded-xl border border-border-default flex items-center justify-center bg-surface-bg">
        <p className="text-body-sm text-content-muted">{t("mapUnavailable")}</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-56 rounded-xl border border-border-default z-0" />
  );
}
