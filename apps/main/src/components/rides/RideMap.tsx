"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import type { Coordinates } from "@fe-el-seka/shared";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import { reverseGeocodeAddress } from "../../lib/geocode";

interface RideMapProps {
  label?: string;
  initialCoordinates?: Coordinates;
  onPinDrop: (coords: Coordinates, address: string) => void;
  fullScreen?: boolean;
}

const CAIRO_CENTER: google.maps.LatLngLiteral = { lat: 30.0444, lng: 31.2357 };

export function RideMap({ label, initialCoordinates, onPinDrop, fullScreen = false }: RideMapProps) {
  const t = useTranslations("map");
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Always-current ref so the map's click listener never captures a stale callback
  const onPinDropRef = useRef(onPinDrop);
  onPinDropRef.current = onPinDrop;
  const [address, setAddress] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const reverseGeocode = useCallback(
    async (lat: number, lng: number) => {
      setLoading(true);
      const addr = (await reverseGeocodeAddress(lat, lng)) ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      setAddress(addr);
      onPinDropRef.current({ lat, lng }, addr);
      setLoading(false);
    },
    [] // stable — reads onPinDrop via ref
  );

  const dropMarker = useCallback((position: google.maps.LatLngLiteral) => {
    const map = mapRef.current;
    if (!map) return;
    if (markerRef.current) {
      markerRef.current.setPosition(position);
    } else {
      markerRef.current = new google.maps.Marker({ position, map });
    }
  }, []);

  const handleMapClick = useCallback(
    (lat: number, lng: number) => {
      dropMarker({ lat, lng });
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => reverseGeocode(lat, lng), 300);
    },
    [dropMarker, reverseGeocode]
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let mounted = true;

    loadGoogleMaps()
      .then(() => {
        if (!mounted || !containerRef.current || mapRef.current) return;

        const center = initialCoordinates ?? CAIRO_CENTER;
        const map = new google.maps.Map(containerRef.current, {
          center,
          zoom: 12,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        });
        mapRef.current = map;

        if (initialCoordinates) {
          markerRef.current = new google.maps.Marker({ position: initialCoordinates, map });
        }

        map.addListener("click", (e: google.maps.MapMouseEvent) => {
          if (!e.latLng) return;
          handleMapClick(e.latLng.lat(), e.latLng.lng());
        });

        if (searchInputRef.current) {
          const autocomplete = new google.maps.places.Autocomplete(searchInputRef.current, {
            componentRestrictions: { country: "eg" },
            fields: ["geometry", "formatted_address"],
          });
          autocomplete.addListener("place_changed", () => {
            const location = autocomplete.getPlace().geometry?.location;
            if (!location) return;

            const position = { lat: location.lat(), lng: location.lng() };
            dropMarker(position);
            map.setCenter(position);
            map.setZoom(15);

            // Places already gives us a formatted address, so this path skips
            // the Nominatim reverse-geocode round-trip (no loading spinner).
            const addr =
              autocomplete.getPlace().formatted_address ??
              `${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}`;
            setAddress(addr);

            // Delay the actual commit (shared with handleMapClick's debounce)
            // so a map tap right after picking a search result still has a
            // window to override the pin before the parent advances fields.
            if (debounceRef.current) clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(() => onPinDropRef.current(position, addr), 300);
          });
        }
      })
      .catch(() => {
        if (mounted) setMapError(true);
      });

    return () => {
      mounted = false;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      markerRef.current?.setMap(null);
      markerRef.current = null;
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const searchInput = (
    <input
      ref={searchInputRef}
      type="text"
      placeholder={t("searchPlaceholder")}
      className="bg-surface-card border border-border-default rounded-full px-4 py-2 text-body-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-primary pointer-events-auto"
    />
  );

  // In fullScreen mode the map is rendered inside pages that also stack a
  // BottomSheet (portaled to document.body at z-50) over the same screen
  // region, and CSS stacking contexts mean no z-index inside RideMap's own
  // subtree can ever outrank that sibling portal. Portal the search box to
  // document.body too, at a higher z-index, so it stays clickable regardless
  // of sheet state.
  const searchBox = fullScreen ? (
    mounted &&
    createPortal(
      <div className="fixed top-3 left-3 right-3 z-[60]">{searchInput}</div>,
      document.body
    )
  ) : (
    <div className="absolute top-3 left-3 right-3 z-[1000]">{searchInput}</div>
  );

  if (mapError) {
    return (
      <div
        className={
          fullScreen
            ? "w-full h-full flex items-center justify-center bg-surface-bg"
            : "w-full h-48 rounded-xl border border-border-default flex items-center justify-center bg-surface-bg"
        }
      >
        <p className="text-body-sm text-content-muted">{t("mapUnavailable")}</p>
      </div>
    );
  }

  if (fullScreen) {
    return (
      <div className="relative w-full h-full">
        {searchBox}
        <div ref={containerRef} className="w-full h-full" />
        {loading && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] bg-surface-card border border-border-default rounded-full px-4 py-2 shadow-sm">
            <p className="text-caption text-content-secondary">{t("gettingAddress")}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {label && <label className="block text-label text-content-secondary">{label}</label>}
      <div className="relative w-full h-48 rounded-xl border border-border-default overflow-hidden">
        {searchBox}
        <div ref={containerRef} className="w-full h-full z-0" />
      </div>
      {loading && <p className="text-caption text-content-muted">{t("gettingAddress")}</p>}
      {address && !loading && (
        <p className="text-caption text-content-secondary truncate" title={address}>
          📍 {address}
        </p>
      )}
    </div>
  );
}
