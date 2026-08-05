"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("rideForm");
  const [origin, setOrigin] = useState<Location | undefined>(initialValues?.origin);
  const [destination, setDestination] = useState<Location | undefined>(initialValues?.destination);
  const [departureRaw, setDepartureRaw] = useState(toDatetimeLocal(initialValues?.departure_datetime));
  const [totalSeats, setTotalSeats] = useState(initialValues?.total_seats ?? 1);
  const [notes, setNotes] = useState(initialValues?.notes ?? "");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Sync external coordinates (from page-level full-screen map) into internal state
  useEffect(() => { if (externalOrigin) setOrigin(externalOrigin); }, [externalOrigin]);
  useEffect(() => { if (externalDestination) setDestination(externalDestination); }, [externalDestination]);

  // Dirty-field detection for edit mode
  useEffect(() => {
    if (mode !== "edit" || !onDirtyChange) return;
    const isDirty =
      departureRaw !== toDatetimeLocal(initialValues?.departure_datetime) ||
      totalSeats !== (initialValues?.total_seats ?? 1) ||
      notes.trim() !== (initialValues?.notes ?? "").trim();
    onDirtyChange(isDirty);
  }, [mode, destination, departureRaw, totalSeats, notes]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleOriginPin = (coords: Coordinates, address: string) => {
    setOrigin({ coordinates: coords, address });
  };

  const handleDestinationPin = (coords: Coordinates, address: string) => {
    setDestination({ coordinates: coords, address });
  };

  const validate = (): string | null => {
    if (!origin) return t("errors.originRequired");
    if (!destination) return t("errors.destinationRequired");
    if (
      Math.abs(origin.coordinates.lat - destination.coordinates.lat) < 1e-5 &&
      Math.abs(origin.coordinates.lng - destination.coordinates.lng) < 1e-5
    ) {
      return t("errors.sameLocation");
    }
    if (!departureRaw) return t("errors.departureRequired");
    const dep = new Date(departureRaw);
    const now = new Date();
    if (dep <= now) return t("errors.departureInPast");
    if (dep > new Date(now.getTime() + 48 * 60 * 60 * 1000))
      return t("errors.departureTooFar");
    if (totalSeats < 1 || totalSeats > maxSeats)
      return t("errors.seatsRange", { maxSeats });
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
        notes: notes.trim() || undefined,
      } as CreateRidePayload);
    } else {
      const payload: EditRidePayload = {};
      if (departureRaw !== toDatetimeLocal(initialValues?.departure_datetime))
        payload.departure_datetime = dep;
      if (totalSeats !== initialValues?.total_seats) payload.total_seats = totalSeats;
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
            <label className="block text-label text-content-secondary">{t("originLabel")}</label>
            {origin ? (
              <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
                <p className="text-body-sm text-content-secondary truncate">📍 {origin.address}</p>
                <button type="button" onClick={onRequestOriginMap} className="text-body-sm text-brand-primary ml-2 shrink-0">
                  {t("change")}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onRequestOriginMap}
                className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-body-sm text-content-muted hover:border-brand-primary transition-colors"
              >
                {t("selectOriginOnMap")}
              </button>
            )}
          </div>
        ) : (
          // Inline map mode (fallback when no page-level map)
          <RideMap
            label={t("originMapLabel")}
            initialCoordinates={initialValues?.origin?.coordinates}
            onPinDrop={handleOriginPin}
          />
        )
      ) : (
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">{t("originLabel")}</label>
          <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
            📍 {initialValues?.origin?.address ?? "—"}
          </p>
          <p className="text-caption text-content-muted">{t("originLockedNote")}</p>
        </div>
      )}

      {mode === "create" ? (
        onRequestDestinationMap ? (
          // External map mode — page owns pin selection via full-screen map
          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("destinationLabel")}</label>
            {destination ? (
              <div className="flex items-center justify-between bg-surface-bg border border-border-default rounded-xl px-3 py-2">
                <p className="text-body-sm text-content-secondary truncate">📍 {destination.address}</p>
                <button type="button" onClick={onRequestDestinationMap} className="text-body-sm text-brand-primary ml-2 shrink-0">
                  {t("change")}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onRequestDestinationMap}
                className="w-full border border-dashed border-border-default rounded-xl px-3 py-4 text-body-sm text-content-muted hover:border-brand-primary transition-colors"
              >
                {t("selectDestinationOnMap")}
              </button>
            )}
          </div>
        ) : (
          <RideMap
            label={t("destinationMapLabel")}
            initialCoordinates={initialValues?.destination?.coordinates}
            onPinDrop={handleDestinationPin}
          />
        )
      ) : (
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">{t("destinationLabel")}</label>
          <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
            📍 {initialValues?.destination?.address ?? "—"}
          </p>
          <p className="text-caption text-content-muted">{t("routeLockedNote")}</p>
        </div>
      )}

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">{t("departureLabel")}</label>
        <input
          type="datetime-local"
          value={departureRaw}
          onChange={(e) => setDepartureRaw(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">
          {t("seatsLabel", { maxSeats })}
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

      <p className="text-caption text-content-muted">
        {t("priceAutoNote")}
      </p>

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">{t("notesLabel")}</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder={t("notesPlaceholder")}
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
          ? mode === "create" ? t("postingRide") : t("savingChanges")
          : mode === "create" ? t("postRide") : t("saveChanges")}
      </button>
    </form>
  );
}
