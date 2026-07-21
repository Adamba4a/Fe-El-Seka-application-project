"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { geocodeAddress, type SearchLocation, type SearchBbox } from "@/lib/geocode";

export type { SearchLocation, SearchBbox };

interface RideSearchFormProps {
  loading?: boolean;
  onSearch: (origin: SearchLocation, destination: SearchLocation) => void;
}

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-sm outline-none focus:border-brand-primary transition-colors bg-surface-card";

export function RideSearchForm({ loading, onSearch }: RideSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);
  const [geocodedOrigin, setGeocodedOrigin] = useState<SearchLocation | null>(null);
  const [geocodedDest, setGeocodedDest] = useState<SearchLocation | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setGeocodedOrigin(null);
    setGeocodedDest(null);

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

      setGeocodedOrigin(origin);
      setGeocodedDest(dest);
      onSearch(origin, dest);
    } finally {
      setGeocoding(false);
    }
  };

  const busy = loading || geocoding;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
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

      {error && <p className="text-sm text-content-destructive">{error}</p>}

      {/* Confirm geocoded locations so user can verify before results load */}
      {(geocodedOrigin || geocodedDest) && !error && (
        <div className="rounded-xl bg-surface-bg border border-border-default px-3 py-2 space-y-1 text-xs text-content-muted">
          {geocodedOrigin && <p>📍 From: <span className="text-content-secondary">{geocodedOrigin.address}</span></p>}
          {geocodedDest && <p>🏁 To: <span className="text-content-secondary">{geocodedDest.address}</span></p>}
        </div>
      )}

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
