"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { formatCurrency } from "@fe-el-seka/shared";
import type {
  CreateRidePayload,
  EditRidePayload,
  CreateRecurringRideDefinitionPayload,
  Location,
  Coordinates,
  Group,
} from "@fe-el-seka/shared";
import { getFareEstimate } from "@/lib/api/pricing";
import { toIsoWeekday } from "@/lib/weekdays";
import { localTimeToUtcTime } from "@/lib/api/recurring-rides";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const; // 0 = Sunday .. 6 = Saturday

const MAX_MARKUP_RATE = 0.3;
function calculateMaxPrice(fairPrice: number): number {
  return Math.round(fairPrice * (1 + MAX_MARKUP_RATE));
}

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
    price_per_seat?: string;
    fair_price_per_seat?: string;
    is_women_only?: boolean;
  };
  maxSeats?: number;
  loading?: boolean;
  error?: string | null;
  // Create mode only — groups the driver belongs to, for the optional group picker (T028).
  groups?: Group[];
  onSubmit: (payload: CreateRidePayload | EditRidePayload) => void;
  // Create mode only (Spec 027) — when provided, a "Recurring" toggle appears; submitting
  // in recurring mode calls this instead of onSubmit. Needs the driver's own vehicle id.
  onSubmitRecurring?: (payload: CreateRecurringRideDefinitionPayload) => void;
  vehicleId?: string;
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
  mode, initialValues, maxSeats = 7, loading, error, groups, onSubmit, onSubmitRecurring, vehicleId, onDirtyChange,
  externalOrigin, externalDestination, onRequestOriginMap, onRequestDestinationMap,
}: RideFormProps) {
  const t = useTranslations("rideForm");
  const locale = useLocale() as "en" | "ar";
  const [origin, setOrigin] = useState<Location | undefined>(initialValues?.origin);
  const [destination, setDestination] = useState<Location | undefined>(initialValues?.destination);
  const [departureRaw, setDepartureRaw] = useState(toDatetimeLocal(initialValues?.departure_datetime));
  const [totalSeats, setTotalSeats] = useState(initialValues?.total_seats ?? 1);
  const [notes, setNotes] = useState(initialValues?.notes ?? "");
  const [groupId, setGroupId] = useState("");
  const [womenOnly, setWomenOnly] = useState(initialValues?.is_women_only ?? false);
  const [journeyType, setJourneyType] = useState<"one_way" | "round_trip">("one_way");
  const [returnDepartureRaw, setReturnDepartureRaw] = useState("");
  const [returnRecurringTime, setReturnRecurringTime] = useState("");
  const [returnSeats, setReturnSeats] = useState(1);
  const [returnFairPrice, setReturnFairPrice] = useState<number | null>(null);
  const [returnMaxPrice, setReturnMaxPrice] = useState<number | null>(null);
  const [returnSelectedPrice, setReturnSelectedPrice] = useState<number | null>(null);
  const [returnFareLoading, setReturnFareLoading] = useState(false);
  const [returnFareError, setReturnFareError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [isRecurring, setIsRecurring] = useState(false);
  const [recurringTime, setRecurringTime] = useState("");
  const [recurringWeekdays, setRecurringWeekdays] = useState<number[]>([]);

  const initialFairPrice = initialValues?.fair_price_per_seat
    ? Number(initialValues.fair_price_per_seat)
    : null;
  const [fairPrice, setFairPrice] = useState<number | null>(initialFairPrice);
  const [maxPrice, setMaxPrice] = useState<number | null>(
    initialFairPrice !== null ? calculateMaxPrice(initialFairPrice) : null
  );
  const [selectedPrice, setSelectedPrice] = useState<number | null>(
    initialValues?.price_per_seat ? Number(initialValues.price_per_seat) : null
  );
  const [fareLoading, setFareLoading] = useState(false);
  const [fareError, setFareError] = useState<string | null>(null);

  // Sync external coordinates (from page-level full-screen map) into internal state
  useEffect(() => { if (externalOrigin) setOrigin(externalOrigin); }, [externalOrigin]);
  useEffect(() => { if (externalDestination) setDestination(externalDestination); }, [externalDestination]);

  // Fetch fare estimate (create mode only — edit mode's route is locked, so the
  // fair price never changes and comes straight from initialValues instead).
  useEffect(() => {
    if (mode !== "create" || !origin || !destination) return;
    let cancelled = false;
    setFareLoading(true);
    setFareError(null);
    getFareEstimate(origin.coordinates, destination.coordinates, totalSeats)
      .then((estimate) => {
        if (cancelled) return;
        setFairPrice(estimate.per_seat_price_egp);
        setMaxPrice(estimate.max_price_per_seat_egp);
        setSelectedPrice(estimate.per_seat_price_egp);
      })
      .catch(() => {
        if (!cancelled) setFareError(t("errors.fareEstimateFailed"));
      })
      .finally(() => {
        if (!cancelled) setFareLoading(false);
      });
    return () => { cancelled = true; };
  }, [mode, origin, destination]); // eslint-disable-line react-hooks/exhaustive-deps

  // A return leg has its own direction and may have a different seat count,
  // so it receives its own calculated base/max range. The driver can only
  // select within that range; they must never type an arbitrary return price.
  useEffect(() => {
    if (mode !== "create" || journeyType !== "round_trip" || !origin || !destination) {
      setReturnFairPrice(null);
      setReturnMaxPrice(null);
      setReturnSelectedPrice(null);
      return;
    }
    let cancelled = false;
    setReturnFareLoading(true);
    setReturnFareError(null);
    getFareEstimate(destination.coordinates, origin.coordinates, returnSeats)
      .then((estimate) => {
        if (cancelled) return;
        setReturnFairPrice(estimate.per_seat_price_egp);
        setReturnMaxPrice(estimate.max_price_per_seat_egp);
        setReturnSelectedPrice(estimate.per_seat_price_egp);
      })
      .catch(() => {
        if (!cancelled) setReturnFareError(t("errors.fareEstimateFailed"));
      })
      .finally(() => {
        if (!cancelled) setReturnFareLoading(false);
      });
    return () => { cancelled = true; };
  }, [mode, journeyType, origin, destination, returnSeats, t]);

  // Dirty-field detection for edit mode
  useEffect(() => {
    if (mode !== "edit" || !onDirtyChange) return;
    const isDirty =
      departureRaw !== toDatetimeLocal(initialValues?.departure_datetime) ||
      totalSeats !== (initialValues?.total_seats ?? 1) ||
      notes.trim() !== (initialValues?.notes ?? "").trim() ||
      womenOnly !== (initialValues?.is_women_only ?? false) ||
      selectedPrice !== (initialValues?.price_per_seat ? Number(initialValues.price_per_seat) : null);
    onDirtyChange(isDirty);
  }, [mode, destination, departureRaw, totalSeats, notes, selectedPrice]); // eslint-disable-line react-hooks/exhaustive-deps

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
    if (mode === "create" && isRecurring) {
      if (!recurringTime) return t("errors.recurringTimeRequired");
      if (recurringWeekdays.length === 0) return t("errors.recurringWeekdaysRequired");
    } else {
      if (!departureRaw) return t("errors.departureRequired");
      const dep = new Date(departureRaw);
      const now = new Date();
      if (dep <= now) return t("errors.departureInPast");
      if (dep > new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000))
        return t("errors.departureTooFar");
    }
    if (totalSeats < 1 || totalSeats > maxSeats)
      return t("errors.seatsRange", { maxSeats });
    if (journeyType === "round_trip") {
      const returnTime = mode === "create" && isRecurring ? returnRecurringTime : returnDepartureRaw;
      if (!returnTime || (mode === "create" && !isRecurring && new Date(returnDepartureRaw) <= new Date(departureRaw))) return t("errors.returnDepartureInvalid");
      if (
        returnSeats < 1 || returnSeats > maxSeats || returnSelectedPrice === null ||
        returnFairPrice === null || returnMaxPrice === null ||
        returnSelectedPrice < returnFairPrice || returnSelectedPrice > returnMaxPrice
      ) return t("errors.returnDetailsInvalid");
    }
    if (mode === "create" && (fairPrice === null || selectedPrice === null))
      return t("errors.fareEstimatePending");
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

    if (mode === "create" && isRecurring) {
      onSubmitRecurring?.({
        vehicle_id: vehicleId!,
        origin: origin!,
        destination: destination!,
        departure_time: localTimeToUtcTime(recurringTime),
        weekdays: recurringWeekdays.map(toIsoWeekday),
        total_seats: totalSeats,
        price_per_seat: selectedPrice!,
        notes: notes.trim() || undefined,
        is_women_only: womenOnly,
        journey_type: journeyType,
        ...(journeyType === "round_trip" ? {
          return_departure_time: localTimeToUtcTime(returnRecurringTime),
          return_total_seats: returnSeats,
          return_price_per_seat: returnSelectedPrice!,
        } : {}),
      });
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
        final_price_per_seat: selectedPrice!,
        group_id: groupId || undefined,
        is_women_only: womenOnly,
        journey_type: journeyType,
        ...(journeyType === "round_trip" ? {
          return_departure_datetime: new Date(returnDepartureRaw).toISOString(),
          return_total_seats: returnSeats,
          return_final_price_per_seat: returnSelectedPrice!,
        } : {}),
      } as CreateRidePayload);
    } else {
      const payload: EditRidePayload = {};
      if (departureRaw !== toDatetimeLocal(initialValues?.departure_datetime))
        payload.departure_datetime = dep;
      if (totalSeats !== initialValues?.total_seats) payload.total_seats = totalSeats;
      if (notes.trim() !== (initialValues?.notes ?? "")) payload.notes = notes.trim();
      const initialPrice = initialValues?.price_per_seat ? Number(initialValues.price_per_seat) : null;
      if (selectedPrice !== null && selectedPrice !== initialPrice)
        payload.final_price_per_seat = selectedPrice;
      if (womenOnly !== (initialValues?.is_women_only ?? false)) payload.is_women_only = womenOnly;
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
                <button type="button" onClick={onRequestOriginMap} className="text-body-sm text-brand-primary ms-2 shrink-0">
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
                <button type="button" onClick={onRequestDestinationMap} className="text-body-sm text-brand-primary ms-2 shrink-0">
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

      {mode === "create" && onSubmitRecurring && (
        <div className="flex items-center justify-between bg-surface-bg rounded-xl px-3 py-3">
          <div>
            <p className="text-label text-content-primary">{t("recurringToggleLabel")}</p>
            <p className="text-caption text-content-muted">{t("recurringToggleHint")}</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={isRecurring}
            onClick={() => setIsRecurring((v) => !v)}
            className={`relative w-11 h-6 rounded-full shrink-0 transition-colors ${
              isRecurring ? "bg-dash-primary" : "bg-border-default"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                isRecurring ? "translate-x-5 rtl:-translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      )}

      {mode === "create" && (
        <div className="space-y-3 rounded-xl bg-surface-bg p-3">
          <label className="flex items-center justify-between text-label text-content-primary">
            <span>{t("womenOnlyLabel")}</span>
            <input type="checkbox" checked={womenOnly} onChange={(e) => setWomenOnly(e.target.checked)} />
          </label>
          <div className="space-y-1">
            <label htmlFor="journey-type" className="block text-label text-content-secondary">{t("journeyTypeLabel")}</label>
            <select id="journey-type" value={journeyType} onChange={(e) => setJourneyType(e.target.value as "one_way" | "round_trip")} className={inputClass}>
              <option value="one_way">{t("oneWay")}</option>
              <option value="round_trip">{t("roundTrip")}</option>
            </select>
          </div>
          {journeyType === "round_trip" && (
            <section className="space-y-4 rounded-xl border border-border-default bg-white p-4">
              <h3 className="text-label text-content-primary">{t("returnJourneyHeading")}</h3>
              <p className="text-caption text-content-muted">{t("returnJourneyHint")}</p>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <label htmlFor="return-departure" className="block text-label text-content-secondary">{t("returnDepartureLabel")}</label>
                  <input id="return-departure" type={isRecurring ? "time" : "datetime-local"} value={isRecurring ? returnRecurringTime : returnDepartureRaw} onChange={(e) => isRecurring ? setReturnRecurringTime(e.target.value) : setReturnDepartureRaw(e.target.value)} className={inputClass} />
                </div>
                <div className="space-y-1">
                  <label htmlFor="return-seats" className="block text-label text-content-secondary">{t("returnSeatsLabel", { maxSeats })}</label>
                  <input id="return-seats" type="number" min={1} max={maxSeats} value={returnSeats} onChange={(e) => setReturnSeats(Number(e.target.value))} className={inputClass} />
                </div>
              </div>
              <div className="space-y-2">
                <label className="block text-label text-content-secondary">{t("returnPriceLabel")}</label>
                {returnFareLoading && <p className="text-body-sm text-content-muted flex items-center gap-2"><Spinner /> {t("priceEstimating")}</p>}
                {returnFareError && <p className="text-body-sm text-content-destructive">{returnFareError}</p>}
                {returnFairPrice !== null && returnMaxPrice !== null && returnSelectedPrice !== null && (
                  <div className="rounded-xl bg-surface-bg px-3 py-3 space-y-2">
                    <div className="flex items-center justify-between text-caption text-content-muted"><span>{t("fairPriceLabel")}</span><span>{formatCurrency(returnFairPrice, locale)}</span></div>
                    {returnFairPrice < returnMaxPrice && <input type="range" min={returnFairPrice} max={returnMaxPrice} step={1} value={returnSelectedPrice} onChange={(e) => setReturnSelectedPrice(Number(e.target.value))} className="w-full accent-dash-primary" />}
                    <div className="flex items-center justify-between"><span className="text-label text-content-primary">{t("selectedPriceLabel")}</span><span className="text-heading-sm text-content-primary font-medium">{formatCurrency(returnSelectedPrice, locale)}</span></div>
                    <div className="flex items-center justify-between text-caption text-content-muted"><span>{t("maxPriceLabel")}</span><span>{formatCurrency(returnMaxPrice, locale)}</span></div>
                  </div>
                )}
                <p className="text-caption text-content-muted">{t("returnPriceHint")}</p>
              </div>
            </section>
          )}
        </div>
      )}

      {mode === "edit" && (
        <label className="flex items-center justify-between rounded-xl bg-surface-bg p-3 text-label text-content-primary"><span>{t("womenOnlyLabel")}</span><input type="checkbox" checked={womenOnly} onChange={(e) => setWomenOnly(e.target.checked)} /></label>
      )}

      {mode === "create" && isRecurring ? (
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("recurringTimeLabel")}</label>
            <input
              type="time"
              value={recurringTime}
              onChange={(e) => setRecurringTime(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("recurringWeekdaysLabel")}</label>
            <div className="flex gap-1.5 flex-wrap">
              {WEEKDAYS.map((day) => {
                const selected = recurringWeekdays.includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() =>
                      setRecurringWeekdays((prev) =>
                        selected ? prev.filter((d) => d !== day) : [...prev, day].sort()
                      )
                    }
                    className={`w-10 h-10 rounded-full text-body-sm font-medium transition-colors ${
                      selected
                        ? "bg-dash-primary text-content-inverse"
                        : "bg-surface-bg text-content-secondary hover:bg-border-default"
                    }`}
                  >
                    {t(`weekdayShort.${day}`)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">{t("departureLabel")}</label>
          <input
            type="datetime-local"
            value={departureRaw}
            onChange={(e) => setDepartureRaw(e.target.value)}
            className={inputClass}
          />
        </div>
      )}

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

      <div className="space-y-2">
        <label className="block text-label text-content-secondary">{t("priceLabel")}</label>
        {mode === "create" && fareLoading && (
          <p className="text-body-sm text-content-muted flex items-center gap-2">
            <Spinner /> {t("priceEstimating")}
          </p>
        )}
        {mode === "create" && fareError && (
          <p className="text-body-sm text-content-destructive">{fareError}</p>
        )}
        {fairPrice !== null && maxPrice !== null && selectedPrice !== null && (
          <div className="bg-surface-bg rounded-xl px-3 py-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-caption text-content-muted">{t("fairPriceLabel")}</span>
              <span className="text-caption text-content-muted">{formatCurrency(fairPrice, locale)}</span>
            </div>
            {fairPrice < maxPrice ? (
              <input
                type="range"
                min={fairPrice}
                max={maxPrice}
                step={1}
                value={selectedPrice}
                onChange={(e) => setSelectedPrice(Number(e.target.value))}
                className="w-full accent-dash-primary"
              />
            ) : null}
            <div className="flex items-center justify-between">
              <span className="text-label text-content-primary">{t("selectedPriceLabel")}</span>
              <span className="text-heading-sm text-content-primary font-medium">
                {formatCurrency(selectedPrice, locale)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-caption text-content-muted">{t("maxPriceLabel")}</span>
              <span className="text-caption text-content-muted">{formatCurrency(maxPrice, locale)}</span>
            </div>
          </div>
        )}
        <p className="text-caption text-content-muted">{t("priceAutoNote")}</p>
      </div>

      {mode === "create" && !isRecurring && groups && groups.length > 0 && (
        <div className="space-y-1">
          <label className="block text-label text-content-secondary">{t("groupLabel")}</label>
          <select
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className={inputClass}
          >
            <option value="">{t("groupNone")}</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
          <p className="text-caption text-content-muted">{t("groupHint")}</p>
        </div>
      )}

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
        className="w-full flex items-center justify-center gap-2 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-opacity"
      >
        {loading && <Spinner />}
        {loading
          ? mode === "create"
            ? isRecurring ? t("postingRecurringRide") : t("postingRide")
            : t("savingChanges")
          : mode === "create"
            ? isRecurring ? t("postRecurringRide") : t("postRide")
            : t("saveChanges")}
      </button>
    </form>
  );
}
