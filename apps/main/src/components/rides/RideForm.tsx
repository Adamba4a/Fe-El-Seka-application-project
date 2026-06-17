"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { CreateRidePayload, EditRidePayload, Location, Coordinates } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("./RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="w-full h-48 bg-gray-100 rounded-lg animate-pulse" /> }
);

interface RideFormProps {
  mode: "create" | "edit";
  initialValues?: {
    origin?: Location;
    destination?: Location;
    departure_datetime?: string;
    total_seats?: number;
    price_per_seat?: string;
    notes?: string;
  };
  maxSeats?: number;
  loading?: boolean;
  error?: string | null;
  onSubmit: (payload: CreateRidePayload | EditRidePayload) => void;
}

function toDatetimeLocal(iso?: string): string {
  if (!iso) return "";
  return iso.substring(0, 16); // "YYYY-MM-DDTHH:MM"
}

export function RideForm({ mode, initialValues, maxSeats = 7, loading, error, onSubmit }: RideFormProps) {
  const [origin, setOrigin] = useState<Location | undefined>(initialValues?.origin);
  const [destination, setDestination] = useState<Location | undefined>(initialValues?.destination);
  const [departureRaw, setDepartureRaw] = useState(toDatetimeLocal(initialValues?.departure_datetime));
  const [totalSeats, setTotalSeats] = useState(initialValues?.total_seats ?? 1);
  const [pricePerSeat, setPricePerSeat] = useState(initialValues?.price_per_seat ?? "");
  const [notes, setNotes] = useState(initialValues?.notes ?? "");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleOriginPin = (coords: Coordinates, address: string) => {
    setOrigin({ coordinates: coords, address });
  };

  const handleDestinationPin = (coords: Coordinates, address: string) => {
    setDestination({ coordinates: coords, address });
  };

  const validate = (): string | null => {
    if (!origin) return "Please select an origin on the map.";
    if (!destination) return "Please select a destination on the map.";
    if (
      Math.abs(origin.coordinates.lat - destination.coordinates.lat) < 1e-5 &&
      Math.abs(origin.coordinates.lng - destination.coordinates.lng) < 1e-5
    ) {
      return "Origin and destination must be different locations.";
    }
    if (!departureRaw) return "Please enter a departure date and time.";
    const dep = new Date(departureRaw);
    const now = new Date();
    if (dep <= now) return "Departure time must be in the future.";
    if (dep > new Date(now.getTime() + 48 * 60 * 60 * 1000))
      return "Rides can only be scheduled up to 48 hours in advance.";
    if (totalSeats < 1 || totalSeats > maxSeats)
      return `Seat count must be between 1 and ${maxSeats}.`;
    const price = parseFloat(pricePerSeat);
    if (!pricePerSeat || isNaN(price) || price <= 0)
      return "Please enter a valid price per seat.";
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    const err = validate();
    if (err) {
      setValidationError(err);
      return;
    }

    const dep = new Date(departureRaw).toISOString();

    if (mode === "create") {
      onSubmit({
        origin: origin!,
        destination: destination!,
        departure_datetime: dep,
        total_seats: totalSeats,
        price_per_seat: parseFloat(pricePerSeat).toFixed(2),
        notes: notes.trim() || undefined,
      } as CreateRidePayload);
    } else {
      const payload: EditRidePayload = {};
      if (destination) payload.destination = destination;
      if (departureRaw !== toDatetimeLocal(initialValues?.departure_datetime))
        payload.departure_datetime = dep;
      if (totalSeats !== initialValues?.total_seats) payload.total_seats = totalSeats;
      if (pricePerSeat !== initialValues?.price_per_seat)
        payload.price_per_seat = parseFloat(pricePerSeat).toFixed(2);
      if (notes.trim() !== (initialValues?.notes ?? "")) payload.notes = notes.trim();
      onSubmit(payload);
    }
  };

  const displayError = validationError ?? error;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {mode === "create" ? (
        <RideMap
          label="Origin (tap to drop pin)"
          initialCoordinates={initialValues?.origin?.coordinates}
          onPinDrop={handleOriginPin}
        />
      ) : (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Origin</label>
          <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
            📍 {initialValues?.origin?.address ?? "—"}
          </p>
          <p className="text-xs text-gray-400">Origin cannot be changed after posting.</p>
        </div>
      )}

      <RideMap
        label="Destination (tap to drop pin)"
        initialCoordinates={initialValues?.destination?.coordinates}
        onPinDrop={handleDestinationPin}
      />

      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">Departure Date &amp; Time</label>
        <input
          type="datetime-local"
          value={departureRaw}
          onChange={(e) => setDepartureRaw(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Seats <span className="text-gray-400">(max {maxSeats})</span>
          </label>
          <input
            type="number"
            min={1}
            max={maxSeats}
            value={totalSeats}
            onChange={(e) => setTotalSeats(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Price/Seat (EGP)</label>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={pricePerSeat}
            onChange={(e) => setPricePerSeat(e.target.value)}
            placeholder="e.g. 45"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">Notes (optional)</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="e.g. No smoking, women only…"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>

      {displayError && (
        <p className="text-sm text-red-600">{displayError}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 text-white rounded-xl py-3 font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading
          ? mode === "create"
            ? "Posting ride…"
            : "Saving changes…"
          : mode === "create"
          ? "Post Ride"
          : "Save Changes"}
      </button>
    </form>
  );
}
