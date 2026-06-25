"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui/Spinner";

export interface SearchLocation {
  lat: number;
  lng: number;
  address: string;
}

interface RideSearchFormProps {
  loading?: boolean;
  onSearch: (origin: SearchLocation, destination: SearchLocation) => void;
}

interface NominatimResult {
  lat: string;
  lon: string;
  display_name: string;
}

async function geocodeAddress(query: string): Promise<SearchLocation | null> {
  const params = new URLSearchParams({ format: "json", q: query, limit: "1", countrycodes: "eg" });
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
    headers: { "Accept-Language": "en" },
  });
  if (!res.ok) return null;
  const results: NominatimResult[] = await res.json();
  if (!results.length) return null;
  const r = results[0];
  return { lat: parseFloat(r.lat), lng: parseFloat(r.lon), address: r.display_name };
}

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-sm outline-none focus:border-brand-primary transition-colors bg-surface-card";

export function RideSearchForm({ loading, onSearch }: RideSearchFormProps) {
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!originText.trim()) { setError("Please enter an origin address."); return; }
    if (!destText.trim()) { setError("Please enter a destination address."); return; }

    setGeocoding(true);
    try {
      const [origin, dest] = await Promise.all([
        geocodeAddress(originText.trim()),
        geocodeAddress(destText.trim()),
      ]);

      if (!origin) { setError("Could not find origin address. Try being more specific."); return; }
      if (!dest) { setError("Could not find destination address. Try being more specific."); return; }

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
