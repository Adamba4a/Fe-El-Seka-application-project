"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { loadGoogleMaps } from "@/lib/google-maps-loader";

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

export function RideDetailMap({
  routeGeometry,
  boardingPoint,
  alightingPoint,
  origin,
  destination,
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

        if (boardingPoint) {
          new google.maps.Polyline({
            ...dashedLineOptions([origin, boardingPoint]),
            map,
          });

          const boardingMarker = new google.maps.Marker({
            position: boardingPoint,
            map,
            icon: circlePinOptions("#16a34a"),
          });
          const boardingInfo = new google.maps.InfoWindow({
            content: t("boarding"),
            disableAutoPan: true,
          });
          boardingMarker.addListener("mouseover", () => boardingInfo.open(map, boardingMarker));
          boardingMarker.addListener("mouseout", () => boardingInfo.close());

          bounds.extend(boardingPoint);
        }

        if (alightingPoint) {
          new google.maps.Polyline({
            ...dashedLineOptions([alightingPoint, destination]),
            map,
          });

          const alightingMarker = new google.maps.Marker({
            position: alightingPoint,
            map,
            icon: circlePinOptions("#dc2626"),
          });
          const alightingInfo = new google.maps.InfoWindow({
            content: t("alighting"),
            disableAutoPan: true,
          });
          alightingMarker.addListener("mouseover", () => alightingInfo.open(map, alightingMarker));
          alightingMarker.addListener("mouseout", () => alightingInfo.close());

          bounds.extend(alightingPoint);
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
