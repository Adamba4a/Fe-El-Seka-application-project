"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { DriverLocationData } from "../../lib/api/location";
import { loadGoogleMaps } from "@/lib/google-maps-loader";

interface LiveTrackingMapProps {
  location: DriverLocationData | null;
  isStale: boolean;
}

const CAIRO_CENTER = { lat: 30.0444, lng: 31.2357 };

type CarMarkerOverlay = google.maps.OverlayView & {
  update(position: google.maps.LatLngLiteral, bearing: number): void;
};
type CarMarkerOverlayCtor = new (position: google.maps.LatLngLiteral, bearing: number) => CarMarkerOverlay;

// Classic Marker can't rotate arbitrary HTML, so the rotating car emoji is a
// custom OverlayView (the direct analogue of Leaflet's divIcon + manual CSS
// transform mutation). Defined lazily since it subclasses google.maps.OverlayView,
// which only exists once the Maps JS API has finished loading.
let carMarkerOverlayCtor: CarMarkerOverlayCtor | null = null;

function getCarMarkerOverlayCtor(): CarMarkerOverlayCtor {
  if (carMarkerOverlayCtor) return carMarkerOverlayCtor;

  class CarMarkerOverlayImpl extends google.maps.OverlayView implements CarMarkerOverlay {
    private div: HTMLDivElement | null = null;

    constructor(private position: google.maps.LatLngLiteral, private bearing: number) {
      super();
    }

    onAdd() {
      const div = document.createElement("div");
      div.style.position = "absolute";
      div.style.fontSize = "24px";
      div.style.lineHeight = "1";
      div.style.transform = `translate(-50%, -50%) rotate(${this.bearing}deg)`;
      div.textContent = "🚗";
      this.div = div;
      this.getPanes()?.overlayMouseTarget.appendChild(div);
    }

    draw() {
      if (!this.div) return;
      const point = this.getProjection()?.fromLatLngToDivPixel(new google.maps.LatLng(this.position));
      if (point) {
        this.div.style.left = `${point.x}px`;
        this.div.style.top = `${point.y}px`;
      }
    }

    onRemove() {
      this.div?.remove();
      this.div = null;
    }

    update(position: google.maps.LatLngLiteral, bearing: number) {
      this.position = position;
      this.bearing = bearing;
      if (this.div) this.div.style.transform = `translate(-50%, -50%) rotate(${bearing}deg)`;
      this.draw();
    }
  }

  carMarkerOverlayCtor = CarMarkerOverlayImpl;
  return carMarkerOverlayCtor;
}

export function LiveTrackingMap({ location, isStale }: LiveTrackingMapProps) {
  const t = useTranslations("map");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const carOverlayRef = useRef<CarMarkerOverlay | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const centeredRef = useRef(false);
  const [mapError, setMapError] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  // Initialize map once on mount
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let mounted = true;

    loadGoogleMaps()
      .then(() => {
        if (!mounted || !containerRef.current || mapRef.current) return;
        mapRef.current = new google.maps.Map(containerRef.current, {
          center: CAIRO_CENTER,
          zoom: 14,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        });
        setMapReady(true);
      })
      .catch(() => {
        if (mounted) setMapError(true);
      });

    return () => {
      mounted = false;
      carOverlayRef.current?.setMap(null);
      carOverlayRef.current = null;
      markerRef.current?.setMap(null);
      markerRef.current = null;
      mapRef.current = null;
      centeredRef.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update marker position whenever location changes, or once the map
  // finishes loading (the API fetch can resolve before the Maps JS script does).
  useEffect(() => {
    if (!location || !mapRef.current) return;
    const map = mapRef.current;
    const position = { lat: location.lat, lng: location.lng };

    if (location.bearing != null) {
      if (markerRef.current) {
        markerRef.current.setMap(null);
        markerRef.current = null;
      }
      if (carOverlayRef.current) {
        carOverlayRef.current.update(position, location.bearing);
      } else {
        const Overlay = getCarMarkerOverlayCtor();
        const overlay = new Overlay(position, location.bearing);
        overlay.setMap(map);
        carOverlayRef.current = overlay;
      }
    } else {
      if (carOverlayRef.current) {
        carOverlayRef.current.setMap(null);
        carOverlayRef.current = null;
      }
      if (markerRef.current) {
        markerRef.current.setPosition(position);
      } else {
        markerRef.current = new google.maps.Marker({ position, map });
      }
    }

    if (!centeredRef.current) {
      map.setCenter(position);
      map.setZoom(15);
      centeredRef.current = true;
    }
  }, [location, mapReady]);

  if (mapError) {
    return (
      <div
        className={`w-full h-full rounded-xl flex items-center justify-center bg-surface-bg ${isStale ? "opacity-75" : ""}`}
      >
        <p className="text-body-sm text-content-muted">{t("mapUnavailable")}</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`w-full h-full rounded-xl z-0 ${isStale ? "opacity-75" : ""}`}
    />
  );
}
