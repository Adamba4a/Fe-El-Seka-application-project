"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import type { SearchLocation, SearchBbox } from "@/lib/geocode";

export type { SearchLocation, SearchBbox };

interface RideSearchFormProps {
  loading?: boolean;
  onSearch: (origin: SearchLocation, destination: SearchLocation, departureAt: string) => void;
  // External coordinate props — when provided, the page owns pin-drop via a full-screen map
  // (mirrors RideForm's externalOrigin/externalDestination pattern)
  externalOrigin?: SearchLocation;
  externalDestination?: SearchLocation;
  onRequestOriginMap?: () => void;
  onRequestDestinationMap?: () => void;
}

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-sm outline-none focus:border-brand-primary transition-colors bg-surface-card";

// datetime-local inputs need "YYYY-MM-DDTHH:mm" in local time, not UTC
function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function placeToSearchLocation(place: google.maps.places.PlaceResult): SearchLocation | null {
  const location = place.geometry?.location;
  if (!location) return null;

  const viewport = place.geometry?.viewport;
  const bbox: SearchBbox | null = viewport
    ? {
        south: viewport.getSouthWest().lat(),
        west: viewport.getSouthWest().lng(),
        north: viewport.getNorthEast().lat(),
        east: viewport.getNorthEast().lng(),
      }
    : null;

  return {
    lat: location.lat(),
    lng: location.lng(),
    address: place.formatted_address ?? `${location.lat().toFixed(5)}, ${location.lng().toFixed(5)}`,
    bbox,
  };
}

export function RideSearchForm({
  loading, onSearch, externalOrigin, externalDestination, onRequestOriginMap, onRequestDestinationMap,
}: RideSearchFormProps) {
  const t = useTranslations("passenger.searchForm");
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [originLocation, setOriginLocation] = useState<SearchLocation | null>(null);
  const [destLocation, setDestLocation] = useState<SearchLocation | null>(null);
  const originInputRef = useRef<HTMLInputElement>(null);
  const destInputRef = useRef<HTMLInputElement>(null);
  const [departureLocal, setDepartureLocal] = useState(() => toDatetimeLocalValue(new Date()));
  const [error, setError] = useState<string | null>(null);

  // Binds Places Autocomplete to the free-text fallback inputs (only rendered
  // when the parent doesn't own pin-drop via onRequestOriginMap/DestinationMap).
  useEffect(() => {
    if (onRequestOriginMap || onRequestDestinationMap) return;
    let cancelled = false;

    loadGoogleMaps().then(() => {
      if (cancelled) return;

      if (originInputRef.current) {
        const autocomplete = new google.maps.places.Autocomplete(originInputRef.current, {
          componentRestrictions: { country: "eg" },
          fields: ["geometry", "formatted_address"],
        });
        autocomplete.addListener("place_changed", () => {
          const location = placeToSearchLocation(autocomplete.getPlace());
          if (!location) return;
          setOriginLocation(location);
          setOriginText(location.address);
        });
      }

      if (destInputRef.current) {
        const autocomplete = new google.maps.places.Autocomplete(destInputRef.current, {
          componentRestrictions: { country: "eg" },
          fields: ["geometry", "formatted_address"],
        });
        autocomplete.addListener("place_changed", () => {
          const location = placeToSearchLocation(autocomplete.getPlace());
          if (!location) return;
          setDestLocation(location);
          setDestText(location.address);
        });
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const departureAt = departureLocal ? new Date(departureLocal).toISOString() : new Date().toISOString();

    if (onRequestOriginMap) {
      // Map-driven mode — origin/destination already resolved via pin-drop
      if (!externalOrigin) { setError(t("errors.originRequired")); return; }
      if (!externalDestination) { setError(t("errors.destinationRequired")); return; }
      if (
        Math.abs(externalOrigin.lat - externalDestination.lat) < 1e-4 &&
        Math.abs(externalOrigin.lng - externalDestination.lng) < 1e-4
      ) {
        setError(t("errors.sameLocation"));
        return;
      }
      onSearch(externalOrigin, externalDestination, departureAt);
      return;
    }

    if (!originText.trim()) { setError(t("errors.originTextRequired")); return; }
    if (!destText.trim()) { setError(t("errors.destTextRequired")); return; }
    if (!originLocation) { setError(t("errors.originNotFound")); return; }
    if (!destLocation) { setError(t("errors.destNotFound")); return; }

    if (
      Math.abs(originLocation.lat - destLocation.lat) < 1e-4 &&
      Math.abs(originLocation.lng - destLocation.lng) < 1e-4
    ) {
      setError(t("errors.sameLocation"));
      return;
    }

    onSearch(originLocation, destLocation, departureAt);
  };

  const busy = loading;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {onRequestOriginMap ? (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">{t("fromLabel")}</label>
          {externalOrigin ? (
            <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
              <p className="text-sm text-content-secondary truncate">📍 {externalOrigin.address}</p>
              <button type="button" onClick={onRequestOriginMap} className="text-sm text-brand-primary ms-2 shrink-0">
                {t("change")}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onRequestOriginMap}
              className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-sm text-content-muted hover:border-brand-primary transition-colors"
            >
              {t("selectOriginOnMap")}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">{t("fromLabel")}</label>
          <input
            ref={originInputRef}
            type="text"
            placeholder={t("fromPlaceholder")}
            value={originText}
            onChange={(e) => { setOriginText(e.target.value); setOriginLocation(null); }}
            className={inputClass}
            disabled={busy}
          />
        </div>
      )}

      {onRequestDestinationMap ? (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">{t("toLabel")}</label>
          {externalDestination ? (
            <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
              <p className="text-sm text-content-secondary truncate">🏁 {externalDestination.address}</p>
              <button type="button" onClick={onRequestDestinationMap} className="text-sm text-brand-primary ms-2 shrink-0">
                {t("change")}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onRequestDestinationMap}
              className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-sm text-content-muted hover:border-brand-primary transition-colors"
            >
              {t("selectDestinationOnMap")}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">{t("toLabel")}</label>
          <input
            ref={destInputRef}
            type="text"
            placeholder={t("toPlaceholder")}
            value={destText}
            onChange={(e) => { setDestText(e.target.value); setDestLocation(null); }}
            className={inputClass}
            disabled={busy}
          />
        </div>
      )}

      <div className="space-y-1">
        <label className="block text-sm font-medium text-content-secondary">{t("departureLabel")}</label>
        <input
          type="datetime-local"
          value={departureLocal}
          min={toDatetimeLocalValue(new Date())}
          onChange={(e) => setDepartureLocal(e.target.value)}
          className={inputClass}
          disabled={busy}
        />
      </div>

      {error && <p className="text-sm text-content-destructive">{error}</p>}

      <button
        type="submit"
        disabled={busy}
        className="w-full flex items-center justify-center gap-2 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-opacity"
      >
        {busy && <Spinner />}
        {busy ? t("searching") : t("searchRides")}
      </button>
    </form>
  );
}
