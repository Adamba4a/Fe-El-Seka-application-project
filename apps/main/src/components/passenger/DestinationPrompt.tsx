"use client";

import { useState } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Spinner } from "@/components/ui/Spinner";
import { geocodeAddress, type SearchLocation } from "@/lib/geocode";

interface DestinationPromptProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (destination: SearchLocation) => void;
}

export function DestinationPrompt({ isOpen, onClose, onConfirm }: DestinationPromptProps) {
  const [destText, setDestText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!destText.trim()) {
      setError("Please enter where you're going.");
      return;
    }

    setGeocoding(true);
    try {
      const dest = await geocodeAddress(destText.trim());
      if (!dest) {
        setError("Could not find that address — try a more specific one (e.g. 'Abbas El Akkad St, Nasr City').");
        return;
      }
      onConfirm(dest);
      setDestText("");
    } finally {
      setGeocoding(false);
    }
  };

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4 pt-1">
        <h2 className="text-lg font-bold text-dash-navy">Where are you going?</h2>
        <p className="text-sm text-dash-text-muted">
          Tell us your drop-off so we can find your boarding and alighting points along this ride's route.
        </p>

        <input
          type="text"
          autoFocus
          placeholder="e.g. Maadi, Cairo"
          value={destText}
          onChange={(e) => setDestText(e.target.value)}
          disabled={geocoding}
          className="w-full border border-dash-border rounded-xl px-3 py-2 text-sm outline-none focus:border-dash-primary transition-colors bg-dash-surface"
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={geocoding}
          className="w-full flex items-center justify-center gap-2 bg-dash-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50 transition-colors"
        >
          {geocoding && <Spinner />}
          {geocoding ? "Locating…" : "Continue"}
        </button>
      </form>
    </BottomSheet>
  );
}
