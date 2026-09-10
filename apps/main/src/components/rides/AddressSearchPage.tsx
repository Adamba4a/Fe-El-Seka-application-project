"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import type { Coordinates } from "@fe-el-seka/shared";
import { loadGoogleMaps } from "@/lib/google-maps-loader";

interface AddressSearchPageProps {
  onSelect: (coords: Coordinates, address: string) => void;
  onClose: () => void;
  onUseMap: () => void;
}

// Full-screen "search results list" experience (Google Maps app style) —
// replaces the old inline search box + native Autocomplete dropdown that
// used to live on top of the map itself. Tapping the map remains available
// as a fallback via onUseMap.
export function AddressSearchPage({ onSelect, onClose, onUseMap }: AddressSearchPageProps) {
  const t = useTranslations("map");
  const [mounted, setMounted] = useState(false);
  const [query, setQuery] = useState("");
  const [predictions, setPredictions] = useState<google.maps.places.AutocompletePrediction[]>([]);
  const [searching, setSearching] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const autocompleteServiceRef = useRef<google.maps.places.AutocompleteService | null>(null);
  const placesServiceRef = useRef<google.maps.places.PlacesService | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let active = true;
    loadGoogleMaps()
      .then(() => {
        if (!active) return;
        autocompleteServiceRef.current = new google.maps.places.AutocompleteService();
        placesServiceRef.current = new google.maps.places.PlacesService(document.createElement("div"));
        inputRef.current?.focus();
      })
      .catch(() => {
        if (active) setLoadError(true);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    if (!trimmed || !autocompleteServiceRef.current) {
      setPredictions([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(() => {
      autocompleteServiceRef.current?.getPlacePredictions(
        { input: trimmed, componentRestrictions: { country: "eg" } },
        (results, status) => {
          setSearching(false);
          setPredictions(status === google.maps.places.PlacesServiceStatus.OK && results ? results : []);
        }
      );
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const handleSelect = (placeId: string, fallbackDescription: string) => {
    if (!placesServiceRef.current) return;
    setResolving(true);
    placesServiceRef.current.getDetails(
      { placeId, fields: ["geometry", "formatted_address"] },
      (place, status) => {
        setResolving(false);
        if (status === google.maps.places.PlacesServiceStatus.OK && place?.geometry?.location) {
          const loc = place.geometry.location;
          onSelect({ lat: loc.lat(), lng: loc.lng() }, place.formatted_address ?? fallbackDescription);
        }
      }
    );
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[70] bg-surface-bg flex flex-col">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border-default shadow-sm shrink-0">
        <button
          type="button"
          onClick={onClose}
          className="text-content-secondary text-xl shrink-0"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchPlaceholder")}
          className="flex-1 bg-transparent focus:outline-none text-body-sm text-content-primary min-w-0"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loadError && (
          <p className="px-4 py-6 text-body-sm text-content-muted text-center">{t("mapUnavailable")}</p>
        )}

        {!loadError && (searching || resolving) && (
          <p className="px-4 py-3 text-caption text-content-muted">{t("gettingAddress")}</p>
        )}

        {!loadError && !searching && query.trim() && predictions.length === 0 && (
          <p className="px-4 py-6 text-body-sm text-content-muted text-center">{t("noResults")}</p>
        )}

        <ul>
          {predictions.map((p) => (
            <li key={p.place_id}>
              <button
                type="button"
                onClick={() => handleSelect(p.place_id, p.description)}
                className="w-full text-start px-4 py-3 flex items-start gap-3 hover:bg-surface-card border-b border-border-default transition-colors"
              >
                <span className="mt-0.5 shrink-0">📍</span>
                <span className="min-w-0">
                  <span className="block text-body-sm text-content-primary truncate">
                    {p.structured_formatting?.main_text ?? p.description}
                  </span>
                  {p.structured_formatting?.secondary_text && (
                    <span className="block text-caption text-content-muted truncate">
                      {p.structured_formatting.secondary_text}
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        onClick={onUseMap}
        className="shrink-0 px-4 py-3 text-body-sm text-brand-primary border-t border-border-default"
      >
        {t("chooseOnMap")}
      </button>
    </div>,
    document.body
  );
}
