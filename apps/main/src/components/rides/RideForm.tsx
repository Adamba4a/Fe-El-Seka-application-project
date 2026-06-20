"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Spinner } from "@/components/ui/Spinner";
import type { CreateRidePayload, EditRidePayload, Location, Coordinates } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("./RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="w-full h-48 bg-surface-bg rounded-xl animate-pulse" /> }
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
  onDirtyChange?: (isDirty: boolean) => void;
  // External coordinate props — when provided, the page owns pin-drop via a full-screen map
  externalOrigin?: Location;
  externalDestination?: Location;
  onRequestOriginMap?: () => void;
  onRequestDestinationMap?: () => void;
}

function toDatetimeLocal(iso?: string): string {
  if (!iso) return "";
  return iso.substring(0, 16);
}

export function RideForm({
  mode, initialValues, maxSeats = 7, loading, error, onSubmit, onDirtyChange,
  externalOrigin, externalDestination, onRequestOriginMap, onRequestDestinationMap,
}: RideFormProps) {
  const [origin, setOrigin] = useState<Location | undefined>(initialValues?.origin);
  const [destination, setDestination] = useState<Location | undefined>(initialValues?.destination);
  const [departureRaw, setDepartureRaw] = useState(toDatetimeLocal(initialValues?.departure_datetime));
  const [totalSeats, setTotalSeats] = useState(initialValues?.total_seats ?? 1);
  const [pricePerSeat, setPricePerSeat] = useState(initialValues?.price_per_seat ?? "");
  const [notes, setNotes] = useState(initialValues?.notes ?? "");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Sync external coordinates (from page-level full-screen map) into internal state
  useEffect(() => { if (externalOrigin) setOrigin(externalOrigin); }, [externalOrigin]);
  useEffect(() => { if (externalDestination) setDestination(externalDestination); }, [externalDestination]);

  // Dirty-field detection for edit mode
  useEffect(() => {
    if (mode !== "edit" || !onDirtyChange) return;
    const isDirty =
      (destination?.address ?? "") !== (initialValues?.destination?.address ?? "") ||
      departureRaw !== toDatetimeLocal(initialValues?.departure_datetime) ||
      totalSeats !== (initialValues?.total_seats ?? 1) ||
      pricePerSeat !== (initialValues?.price_per_seat ?? "") ||
      notes.trim() !== (initialValues?.notes ?? "").trim();
    onDirtyChange(isDirty);
  }, [mode, destination, departureRaw, totalSeats, pricePerSeat, notes]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const inputClass = "w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus transition-colors";

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {mode === "create" ? (
        onRequestOriginMap ? (
          // External map mode — page owns pin selection via full-screen map
          <div className="space-y-1">
            <label className="block text-label text-content-secondary">Origin</label>
            {origin ? (
              <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
                <p className="text-body-sm text-content-secondary truncate">📍 {origin.address}</p>
                <button type="button" onClick={onRequestOriginMap} className="text-body-sm text-brand-primary ml-2 shrink-0">
                  Change
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onRequestOriginMap}
                className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-body-sm text-content-muted hover:border-brand-primary transition-colors"
              >
                📍 Select origin on map
              </button>
            )}
          </div>
        ) : (
          // Inline map mode (fallback when no page-level map)
          <RideMap
            label="Origin (tap to drop pin)"
            initialCoordinates={initialValues?.origin?.coordinates}
            onPinDrop={handleOriginPin}
          />
        )
      ) : (
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">Origin</label>
          <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
            📍 {initialValues?.origin?.address ?? "—"}
          </p>
          <p className="text-caption text-content-muted">Origin cannot be changed after posting.</p>
        </div>
      )}

      {mode === "create" && onRequestDestinationMap ? (
        // External map mode — page owns pin selection via full-screen map
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">Destination</label>
          {destination ? (
            <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
              <p className="text-body-sm text-content-secondary truncate">📍 {destination.address}</p>
              <button type="button" onClick={onRequestDestinationMap} className="text-body-sm text-brand-primary ml-2 shrink-0">
                Change
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onRequestDestinationMap}
              className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-body-sm text-content-muted hover:border-brand-primary transition-colors"
            >
              📍 Select destination on map
            </button>
          )}
        </div>
      ) : (
        <RideMap
          label="Destination (tap to drop pin)"
          initialCoordinates={initialValues?.destination?.coordinates}
          onPinDrop={handleDestinationPin}
        />
      )}

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">Departure Date &amp; Time</label>
        <input
          type="datetime-local"
          value={departureRaw}
          onChange={(e) => setDepartureRaw(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">
            Seats <span className="text-content-muted">(max {maxSeats})</span>
          </label>
          <input
            type="number"
            min={1}
            max={maxSeats}
            value={totalSeats}
            onChange={(e) => setTotalSeats(Number(e.target.value))}
            className={inputClass}
          />
        </div>

        <div className="space-y-1">
          <label className="block text-label text-content-secondary">EGP per seat</label>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={pricePerSeat}
            onChange={(e) => setPricePerSeat(e.target.value)}
            placeholder="e.g. 45"
            className={inputClass}
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">Notes (optional)</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="e.g. No smoking, women only…"
          className={`${inputClass} resize-none`}
        />
      </div>

      {displayError && (
        <p className="text-body-sm text-content-destructive">{displayError}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
      >
        {loading && <Spinner />}
        {loading
          ? mode === "create" ? "Posting ride…" : "Saving changes…"
          : mode === "create" ? "Post Ride" : "Save Changes"}
      </button>
    </form>
  );
}
