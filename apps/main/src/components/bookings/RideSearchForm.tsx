"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { geocodeAddress, type SearchLocation, type SearchBbox } from "@/lib/geocode";

export type { SearchLocation, SearchBbox };

interface RideSearchFormProps {
  loading?: boolean;
  onSearch: (origin: SearchLocation, destination: SearchLocation) => void;
  // External coordinate props — when provided, the page owns pin-drop via a full-screen map
  // (mirrors RideForm's externalOrigin/externalDestination pattern)
  externalOrigin?: SearchLocation;
  externalDestination?: SearchLocation;
  onRequestOriginMap?: () => void;
  onRequestDestinationMap?: () => void;
}

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-sm outline-none focus:border-brand-primary transition-colors bg-surface-card";

export function RideSearchForm({
  loading, onSearch, externalOrigin, externalDestination, onRequestOriginMap, onRequestDestinationMap,
}: RideSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (onRequestOriginMap) {
      // Map-driven mode — origin/destination already resolved via pin-drop
      if (!externalOrigin) { setError("Please select an origin on the map."); return; }
      if (!externalDestination) { setError("Please select a destination on the map."); return; }
      if (
        Math.abs(externalOrigin.lat - externalDestination.lat) < 1e-4 &&
        Math.abs(externalOrigin.lng - externalDestination.lng) < 1e-4
      ) {
        setError("Origin and destination must be different locations.");
        return;
      }
      onSearch(externalOrigin, externalDestination);
      return;
    }

    if (!originText.trim()) { setError("Please enter an origin address."); return; }
    if (!destText.trim()) { setError("Please enter a destination address."); return; }

    setGeocoding(true);
    try {
      const [origin, dest] = await Promise.all([
        geocodeAddress(originText.trim()),
        geocodeAddress(destText.trim()),
      ]);

      if (!origin) { setError("Could not find origin — try a more specific address (e.g. 'Abbas El Akkad St, Nasr City')."); return; }
      if (!dest) { setError("Could not find destination — try a more specific address (e.g. 'Abbas El Akkad St, Nasr City')."); return; }

      if (Math.abs(origin.lat - dest.lat) < 1e-4 && Math.abs(origin.lng - dest.lng) < 1e-4) {
        setError("Origin and destination must be different locations.");
        return;
      }

      onSearch(origin, dest);
    } finally {
      setGeocoding(false);
    }
  };

  const busy = loading || geocoding;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {onRequestOriginMap ? (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">From</label>
          {externalOrigin ? (
            <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
              <p className="text-sm text-content-secondary truncate">📍 {externalOrigin.address}</p>
              <button type="button" onClick={onRequestOriginMap} className="text-sm text-brand-primary ml-2 shrink-0">
                Change
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onRequestOriginMap}
              className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-sm text-content-muted hover:border-brand-primary transition-colors"
            >
              📍 Select origin on map
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">From</label>
          <input
            type="text"
            placeholder="e.g. Nasr City, Cairo"
            value={originText}
            onChange={(e) => setOriginText(e.target.value)}
            className={inputClass}
            disabled={busy}
          />
        </div>
      )}

      {onRequestDestinationMap ? (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">To</label>
          {externalDestination ? (
            <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
              <p className="text-sm text-content-secondary truncate">🏁 {externalDestination.address}</p>
              <button type="button" onClick={onRequestDestinationMap} className="text-sm text-brand-primary ml-2 shrink-0">
                Change
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onRequestDestinationMap}
              className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-sm text-content-muted hover:border-brand-primary transition-colors"
            >
              🏁 Select destination on map
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-content-secondary">To</label>
          <input
            type="text"
            placeholder="e.g. Maadi, Cairo"
            value={destText}
            onChange={(e) => setDestText(e.target.value)}
            className={inputClass}
            disabled={busy}
          />
        </div>
      )}

      {error && <p className="text-sm text-content-destructive">{error}</p>}

      <button
        type="submit"
        disabled={busy}
        className="w-full flex items-center justify-center gap-2 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
      >
        {busy && <Spinner />}
        {busy ? "Searching…" : "Search Rides"}
      </button>
    </form>
  );
}
