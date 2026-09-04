"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { MatchScoreBadge } from "@/components/search/MatchScoreBadge";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { VerificationRequiredModal } from "@/components/verification/VerificationRequiredModal";
import Link from "next/link";
import { env } from "@/lib/env";
import { getDeviceId } from "@/lib/device-id";
import { formatCurrency, FARE_SPLIT_SEATS } from "@fe-el-seka/shared";
import type { Locale } from "@fe-el-seka/shared";
import { fromIsoWeekday } from "@/lib/weekdays";
import { listRecurringInstancesForRide, type RecurringInstanceOption } from "@/lib/api/recurring-rides";
import { getLoyaltyBalance } from "@/lib/api/loyalty";

const RideDetailMap = dynamic(
  () => import("@/components/bookings/RideDetailMap").then((m) => ({ default: m.RideDetailMap })),
  { ssr: false, loading: () => <div className="w-full h-56 bg-surface-bg rounded-xl animate-pulse" /> }
);

interface DriverInfo {
  id: string;
  display_name: string | null;
  avatar_url: string | null;
  is_verified: boolean;
  rating_avg: number | null;
  rating_count: number;
}

interface PassengerContext {
  boarding_point: { lat: number; lng: number };
  alighting_point: { lat: number; lng: number };
  pickup_walk_meters: number;
  dropoff_walk_meters: number;
  estimated_travel_minutes: number | null;
  premium_pickup_available: boolean;
  premium_pickup_fee: number | null;
  premium_dropoff_available: boolean;
  premium_dropoff_fee: number | null;
}

interface ExistingBooking {
  booking_id: string;
  status: string;
  seats: number;
}

interface RideDetail {
  id: string;
  status: string;
  driver: DriverInfo;
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  fuel_cost_egp: number | null;
  route_geometry: object | null;
  route_distance_km: number;
  route_duration_minutes: number;
  is_sponsored: boolean;
  group_id: string | null;
  group_name: string | null;
  recurring_ride_definition_id: string | null;
  recurring_weekdays: number[] | null;
}

interface DetailResponse {
  ride: RideDetail;
  passenger_context: PassengerContext;
  match_score_pct: number | null;
  existing_booking: ExistingBooking | null;
}

interface PreviewRide {
  id: string;
  status: string;
  driver: DriverInfo;
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  origin_address: string;
  destination_address: string;
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
  route_geometry: object | null;
  route_distance_km: number;
  route_duration_minutes: number | null;
  existing_booking: ExistingBooking | null;
  recurring_ride_definition_id: string | null;
  recurring_weekdays: number[] | null;
}

type PremiumOption = "standard" | "premium_pickup" | "premium_dropoff" | "premium_both";

function RecurringSeriesNote({
  definitionId,
  weekdays,
  t,
}: {
  definitionId: string | null;
  weekdays: number[] | null;
  t: ReturnType<typeof useTranslations>;
}) {
  if (!definitionId) return null;
  const dayLabels = (weekdays ?? [])
    .map((d) => t(`weekdayShort.${fromIsoWeekday(d)}`))
    .join(", ");
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-bg border border-border-default text-xs text-content-secondary">
      <span className="font-medium text-content-primary">{t("recurringSeriesLabel")}</span>
      {dayLabels && <span>· {t("recurringSeriesOtherDays", { days: dayLabels })}</span>}
    </div>
  );
}

function formatDeparture(iso: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

function formatDayLabel(iso: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

function RecurringDayPicker({
  instances,
  currentRideId,
  extraSeats,
  onToggle,
  onSeatsChange,
  locale,
  t,
}: {
  instances: RecurringInstanceOption[];
  currentRideId: string;
  extraSeats: Record<string, number>;
  onToggle: (instance: RecurringInstanceOption) => void;
  onSeatsChange: (rideId: string, seats: number) => void;
  locale: Locale;
  t: ReturnType<typeof useTranslations>;
}) {
  const otherDays = instances.filter((i) => i.ride_id !== currentRideId);
  if (otherDays.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-content-primary">{t("recurringPickerHeading")}</p>
      <p className="text-xs text-content-muted">{t("recurringPickerHint")}</p>
      <div className="space-y-2">
        {otherDays.map((inst) => {
          const alreadyBooked = !!inst.existing_booking;
          const full = inst.available_seats === 0;
          const disabled = alreadyBooked || full;
          const selected = inst.ride_id in extraSeats;
          const maxSeats = Math.min(inst.available_seats, 8);
          const seats = extraSeats[inst.ride_id] ?? 1;

          return (
            <div
              key={inst.ride_id}
              className={`rounded-xl border p-3 transition-colors ${
                selected ? "border-brand-primary bg-brand-primary/5" : "border-border-default bg-surface-card"
              } ${disabled ? "opacity-60" : ""}`}
            >
              <button
                type="button"
                disabled={disabled}
                onClick={() => onToggle(inst)}
                className="w-full flex items-center justify-between text-sm disabled:cursor-not-allowed"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`w-5 h-5 rounded-md border flex items-center justify-center text-xs ${
                      selected ? "bg-brand-primary border-brand-primary text-content-inverse" : "border-border-default"
                    }`}
                  >
                    {selected ? "✓" : ""}
                  </span>
                  <span className="font-medium text-content-primary">{formatDayLabel(inst.departure_datetime, locale)}</span>
                </span>
                <span className="text-xs text-content-muted">
                  {alreadyBooked
                    ? t("alreadyBooked")
                    : full
                    ? t("full")
                    : t("seatsLeft", { count: inst.available_seats })}
                </span>
              </button>

              {selected && !disabled && (
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-border-default/60">
                  <span className="text-xs text-content-secondary">{t("numberOfSeats")}</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onSeatsChange(inst.ride_id, Math.max(1, seats - 1))}
                      disabled={seats <= 1}
                      className="w-6 h-6 rounded-full border border-border-default text-content-primary disabled:opacity-40 hover:bg-surface-bg transition-colors text-xs"
                    >
                      −
                    </button>
                    <span className="w-5 text-center text-xs font-semibold text-content-primary">{seats}</span>
                    <button
                      type="button"
                      onClick={() => onSeatsChange(inst.ride_id, Math.min(maxSeats, seats + 1))}
                      disabled={seats >= maxSeats}
                      className="w-6 h-6 rounded-full border border-border-default text-content-primary disabled:opacity-40 hover:bg-surface-bg transition-colors text-xs"
                    >
                      +
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function PassengerRideDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("passenger.rideDetail");
  const tRideCard = useTranslations("rideCard");
  const locale = useLocale() as Locale;

  // No origin/dest in the URL yet → this is a bare dashboard-card click, show
  // the lightweight preview instead of the full pickup/dropoff match view.
  const hasParams = searchParams.has("origin_lat") && searchParams.has("dest_lat");

  const originLat = parseFloat(searchParams.get("origin_lat") ?? "30.0626");
  const originLng = parseFloat(searchParams.get("origin_lng") ?? "31.2497");
  const destLat = parseFloat(searchParams.get("dest_lat") ?? "30.0444");
  const destLng = parseFloat(searchParams.get("dest_lng") ?? "31.2357");
  const departureAt = searchParams.get("departure_at");

  const [detail, setDetail] = useState<DetailResponse | null>(null);
  const [preview, setPreview] = useState<PreviewRide | null>(null);
  const [loading, setLoading] = useState(true);
  const [gone, setGone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [premiumOption, setPremiumOption] = useState<PremiumOption>("standard");
  const [seatCount, setSeatCount] = useState(1);
  const [showSheet, setShowSheet] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [siblingInstances, setSiblingInstances] = useState<RecurringInstanceOption[]>([]);
  const [extraSeats, setExtraSeats] = useState<Record<string, number>>({});
  const [loyaltyBalance, setLoyaltyBalance] = useState<number | null>(null);
  const [pointsToRedeem, setPointsToRedeem] = useState(0);

  useEffect(() => {
    async function load() {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }

        if (!hasParams) {
          const res = await fetch(`${env.apiUrl}/api/v1/rides/${id}/preview`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });

          if (res.status === 410 || res.status === 404) { setGone(true); return; }
          if (!res.ok) { setError(t("errors.loadFailed")); return; }

          const json = await res.json();
          setPreview(json.ride);
          return;
        }

        const params = new URLSearchParams({
          origin_lat: String(originLat),
          origin_lng: String(originLng),
          destination_lat: String(destLat),
          destination_lng: String(destLng),
          ...(departureAt ? { departure_at: departureAt } : {}),
        });

        const res = await fetch(`${env.apiUrl}/api/v1/rides/${id}/passenger-detail?${params}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });

        if (res.status === 410) { setGone(true); return; }
        if (!res.ok) { setError(t("errors.loadFailed")); return; }

        const json: DetailResponse = await res.json();
        setDetail(json);
      } catch {
        setError(t("errors.network"));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, hasParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    async function loadSiblings() {
      if (!detail?.ride.recurring_ride_definition_id) return;
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const { instances } = await listRecurringInstancesForRide(session.access_token, String(id));
        setSiblingInstances(instances);
      } catch {
        // Non-critical: the day-picker just stays hidden if this fails.
      }
    }
    loadSiblings();
  }, [id, detail?.ride.recurring_ride_definition_id]);

  useEffect(() => {
    async function loadLoyalty() {
      if (!detail || detail.ride.is_sponsored) return;
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const balance = await getLoyaltyBalance(session.access_token);
        setLoyaltyBalance(balance.balance);
      } catch {
        // Non-critical: the points stepper just stays hidden if this fails.
      }
    }
    loadLoyalty();
  }, [detail]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (gone) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="text-lg font-semibold text-content-primary">{t("rideNoLongerAvailableTitle")}</p>
        <p className="text-sm text-content-muted">{t("rideNoLongerAvailableBody")}</p>
        <button
          onClick={() => router.push("/search")}
          className="text-sm text-brand-primary font-medium"
        >
          {t("searchAnotherRide")}
        </button>
      </div>
    );
  }

  if (!hasParams) {
    if (error || !preview) {
      return (
        <div className="py-16 text-center">
          <p className="text-sm text-content-destructive">{error ?? t("errors.somethingWrong")}</p>
        </div>
      );
    }

    const noSeats = preview.available_seats === 0;

    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          className="text-content-muted hover:text-content-secondary text-sm"
        >
          {t("back")}
        </button>

        <div className="flex items-center gap-3 p-4 bg-surface-card border border-border-default rounded-xl">
          {preview.driver.avatar_url ? (
            <img
              src={preview.driver.avatar_url}
              alt={preview.driver.display_name ?? t("driver")}
              className="w-12 h-12 rounded-full object-cover shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-base font-semibold text-content-secondary">
              {(preview.driver.display_name ?? "?")[0].toUpperCase()}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-content-primary truncate">
              {preview.driver.display_name ?? t("driver")}
            </p>
            <div className="flex items-center gap-2">
              {preview.driver.is_verified && (
                <span className="text-xs text-green-600 font-medium">{t("verifiedDriver")}</span>
              )}
              <RatingBadge ratingAvg={preview.driver.rating_avg} ratingCount={preview.driver.rating_count} />
            </div>
          </div>
          <Link
            href={`/users/${preview.driver.id}`}
            className="shrink-0 rounded-xl bg-dash-primary px-3 py-2 text-xs font-semibold text-content-inverse hover:opacity-90 transition-opacity"
          >
            {t("viewProfile")}
          </Link>
        </div>

        <RecurringSeriesNote
          definitionId={preview.recurring_ride_definition_id}
          weekdays={preview.recurring_weekdays}
          t={t}
        />

        <RideDetailMap
          routeGeometry={preview.route_geometry}
          boardingPoint={null}
          alightingPoint={null}
          origin={preview.origin}
          destination={preview.destination}
        />

        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-content-secondary">
            <span>{t("route")}</span>
            <span className="font-medium text-content-primary text-end">
              {preview.origin_address} → {preview.destination_address}
            </span>
          </div>
          <div className="flex justify-between text-content-secondary">
            <span>{t("departure")}</span>
            <span className="font-medium text-content-primary">{formatDeparture(preview.departure_datetime, locale)}</span>
          </div>
          {preview.route_duration_minutes != null && (
            <div className="flex justify-between text-content-secondary">
              <span>{t("rideTime")}</span>
              <span className="font-medium text-content-primary">{t("minutesShort", { minutes: preview.route_duration_minutes })}</span>
            </div>
          )}
          <div className="flex justify-between text-content-secondary">
            <span>{t("availableSeats")}</span>
            <span className={`font-medium ${noSeats ? "text-content-destructive" : "text-content-primary"}`}>
              {noSeats ? t("full") : preview.available_seats}
            </span>
          </div>
          <div className="flex justify-between text-content-secondary">
            <span>{t("pricePerSeat")}</span>
            <span className="font-medium text-content-primary">{formatCurrency(Number(preview.per_seat_price), locale)}</span>
          </div>
        </div>

        {preview.existing_booking ? (
          <div className="space-y-2 p-4 rounded-xl bg-surface-bg border border-border-default">
            <p className="text-sm font-medium text-content-primary">{t("existingBookingTitle")}</p>
            <p className="text-xs text-content-muted">{t("existingBookingBody")}</p>
            <Link
              href={`/bookings/${preview.existing_booking.booking_id}`}
              className="block w-full text-center bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
            >
              {t("manageBooking")}
            </Link>
          </div>
        ) : (
          <button
            type="button"
            disabled={noSeats}
            onClick={() => {
              const params = new URLSearchParams({ departure_at: preview.departure_datetime });
              router.push(`/rides/${id}/book?${params}`);
            }}
            className="w-full bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-opacity"
          >
            {noSeats ? t("noSeatsAvailable") : t("bookSeat")}
          </button>
        )}
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-content-destructive">{error ?? t("errors.somethingWrong")}</p>
      </div>
    );
  }

  const { ride, passenger_context: ctx } = detail;
  const hasPremium = ctx.premium_pickup_available || ctx.premium_dropoff_available;

  const premiumFee = (() => {
    if (premiumOption === "premium_pickup") return ctx.premium_pickup_fee ?? 0;
    if (premiumOption === "premium_dropoff") return ctx.premium_dropoff_fee ?? 0;
    if (premiumOption === "premium_both")
      return (ctx.premium_pickup_fee ?? 0) + (ctx.premium_dropoff_fee ?? 0);
    return 0;
  })();

  const maxSeats = ride.is_sponsored ? 1 : Math.min(ride.available_seats, 8);
  const clampedSeatCount = Math.max(1, Math.min(seatCount, maxSeats || 1));
  const extraTotal = Object.entries(extraSeats).reduce((sum, [rideId, seats]) => {
    const inst = siblingInstances.find((i) => i.ride_id === rideId);
    if (!inst) return sum;
    return sum + parseFloat(inst.per_seat_price) * seats + premiumFee;
  }, 0);
  const totalPriceBeforePoints = parseFloat(ride.per_seat_price) * clampedSeatCount + premiumFee + extraTotal;
  const maxPointsDiscountEgp = Math.min(
    ((ride.fuel_cost_egp ?? 0) / FARE_SPLIT_SEATS) * clampedSeatCount,
    totalPriceBeforePoints
  );
  const maxPointsRedeemable = Math.max(0, Math.min(loyaltyBalance ?? 0, Math.floor(maxPointsDiscountEgp)));
  const clampedPointsToRedeem = Math.min(pointsToRedeem, maxPointsRedeemable);
  const totalPrice = (totalPriceBeforePoints - clampedPointsToRedeem).toFixed(2);
  const noSeats = ride.available_seats === 0;
  const selectedExtraCount = Object.keys(extraSeats).length;
  const pointsRedemptionAvailable = !ride.is_sponsored && selectedExtraCount === 0;

  const handleBook = () => {
    setBookingError(null);
    setShowSheet(true);
  };

  const toggleExtraDay = (inst: RecurringInstanceOption) => {
    setExtraSeats((prev) => {
      const next = { ...prev };
      if (inst.ride_id in next) {
        delete next[inst.ride_id];
      } else {
        next[inst.ride_id] = Math.min(1, Math.max(1, Math.min(inst.available_seats, 8)));
      }
      return next;
    });
  };

  const setExtraDaySeats = (rideId: string, seats: number) => {
    setExtraSeats((prev) => ({ ...prev, [rideId]: seats }));
  };

  const confirmBooking = async () => {
    if (!detail) return;
    setBookingLoading(true);
    setBookingError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }

      const ctx = detail.passenger_context;
      const pickupFee = premiumOption === "premium_pickup" || premiumOption === "premium_both"
        ? ctx.premium_pickup_fee : null;
      const dropoffFee = premiumOption === "premium_dropoff" || premiumOption === "premium_both"
        ? ctx.premium_dropoff_fee : null;

      const postBooking = async (
        rideId: string,
        seats: number,
        loyaltyRedemptionCatalogEntryId: string | null,
        pointsToRedeemForTarget: number | null
      ): Promise<{ res: Response; json: { booking_id?: string; detail?: unknown; error?: string; message?: string } }> => {
        const deviceId = getDeviceId();
        const res = await fetch(`${env.apiUrl}/api/v1/bookings`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
            ...(deviceId ? { "X-Device-Id": deviceId } : {}),
          },
          body: JSON.stringify({
            ride_id: rideId,
            boarding_point: ctx.boarding_point,
            alighting_point: ctx.alighting_point,
            premium_pickup_requested: premiumOption === "premium_pickup" || premiumOption === "premium_both",
            premium_dropoff_requested: premiumOption === "premium_dropoff" || premiumOption === "premium_both",
            premium_pickup_fee: pickupFee,
            premium_dropoff_fee: dropoffFee,
            seats,
            loyalty_redemption_catalog_entry_id: loyaltyRedemptionCatalogEntryId,
            points_to_redeem: pointsToRedeemForTarget,
          }),
        });
        const json = await res.json();
        return { res, json };
      };

      // Points redemption only applies to the single main-day booking — not
      // to extra recurring days, which are separate bookings on separate rides.
      const extraDayCount = Object.keys(extraSeats).length;
      const targets = [
        {
          rideId: detail.ride.id,
          seats: clampedSeatCount,
          loyaltyRedemptionCatalogEntryId: null as string | null,
          pointsToRedeem: extraDayCount === 0 && clampedPointsToRedeem > 0 ? clampedPointsToRedeem : null,
        },
        ...Object.entries(extraSeats).map(([rideId, seats]) => ({
          rideId,
          seats,
          loyaltyRedemptionCatalogEntryId: null as string | null,
          pointsToRedeem: null as number | null,
        })),
      ];

      const outcomes: Awaited<ReturnType<typeof postBooking>>[] = [];
      for (const target of targets) {
        outcomes.push(
          await postBooking(target.rideId, target.seats, target.loyaltyRedemptionCatalogEntryId, target.pointsToRedeem)
        );
      }

      const succeeded = outcomes.filter((o) => o.res.status === 201);
      const failed = outcomes.filter((o) => o.res.status !== 201);

      if (succeeded.length === 0) {
        const { res, json } = outcomes[0];
        const err = (
          json && typeof json === "object" && json.detail && typeof json.detail === "object"
            ? json.detail
            : json
        ) as { error?: string; message?: string };
        if (res.status === 403 && err?.error === "verification_required") {
          setShowSheet(false);
          setShowVerifyModal(true);
        } else if (res.status === 409) {
          setBookingError(
            err?.error === "duplicate_booking"
              ? t("errors.duplicateBooking")
              : err?.error === "insufficient_points"
              ? t("errors.insufficientPoints")
              : err?.error === "loyalty_redemption_conflict"
              ? t("errors.loyaltyConflict")
              : t("errors.noSeats")
          );
        } else {
          setBookingError(err?.message ?? t("errors.bookingFailed"));
        }
        return;
      }

      if (failed.length > 0) {
        window.alert(t("errors.partialBookingFailure", { succeeded: succeeded.length, total: outcomes.length }));
      }

      if (succeeded.length === 1 && failed.length === 0) {
        router.push(`/bookings/${succeeded[0].json.booking_id}`);
      } else {
        router.push("/bookings");
      }
    } catch {
      setBookingError(t("errors.networkBooking"));
    } finally {
      setBookingLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => router.back()}
        className="text-content-muted hover:text-content-secondary text-sm"
      >
        {t("backToResults")}
      </button>

      {/* Driver card */}
      <div className="flex items-center gap-3 p-4 bg-surface-card border border-border-default rounded-xl">
        {ride.driver.avatar_url ? (
          <img
            src={ride.driver.avatar_url}
            alt={ride.driver.display_name ?? t("driver")}
            className="w-12 h-12 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-base font-semibold text-content-secondary">
            {(ride.driver.display_name ?? "?")[0].toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-content-primary truncate">
            {ride.driver.display_name ?? t("driver")}
          </p>
          <div className="flex items-center gap-2">
            {ride.driver.is_verified && (
              <span className="text-xs text-green-600 font-medium">{t("verifiedDriver")}</span>
            )}
            <RatingBadge ratingAvg={ride.driver.rating_avg} ratingCount={ride.driver.rating_count} />
          </div>
        </div>
        <Link
          href={`/users/${ride.driver.id}`}
          className="shrink-0 rounded-xl bg-dash-primary px-3 py-2 text-xs font-semibold text-content-inverse hover:opacity-90 transition-opacity"
        >
          {t("viewProfile")}
        </Link>
      </div>

      {ride.group_name && (
        <span className="inline-block text-xs font-semibold bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
          {tRideCard("groupRide", { name: ride.group_name })}
        </span>
      )}

      {detail.match_score_pct !== null && (
        <MatchScoreBadge score_pct={detail.match_score_pct} />
      )}

      <RecurringSeriesNote
        definitionId={ride.recurring_ride_definition_id}
        weekdays={ride.recurring_weekdays}
        t={t}
      />

      {ride.recurring_ride_definition_id && !detail.existing_booking && (
        <RecurringDayPicker
          instances={siblingInstances}
          currentRideId={ride.id}
          extraSeats={extraSeats}
          onToggle={toggleExtraDay}
          onSeatsChange={setExtraDaySeats}
          locale={locale}
          t={t}
        />
      )}

      {/* Map */}
      <RideDetailMap
        routeGeometry={ride.route_geometry}
        boardingPoint={ctx.boarding_point}
        alightingPoint={ctx.alighting_point}
        origin={{ lat: originLat, lng: originLng }}
        destination={{ lat: destLat, lng: destLng }}
      />

      {/* Ride info */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between text-content-secondary">
          <span>{t("departure")}</span>
          <span className="font-medium text-content-primary">{formatDeparture(ride.departure_datetime, locale)}</span>
        </div>
        {ctx.estimated_travel_minutes && (
          <div className="flex justify-between text-content-secondary">
            <span>{t("estimatedRideTime")}</span>
            <span className="font-medium text-content-primary">{t("minutesShort", { minutes: ctx.estimated_travel_minutes })}</span>
          </div>
        )}
        <div className="flex justify-between text-content-secondary">
          <span>{t("walkToPickup")}</span>
          <span className="font-medium text-content-primary">{ctx.pickup_walk_meters}m</span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>{t("walkFromDropoff")}</span>
          <span className="font-medium text-content-primary">{ctx.dropoff_walk_meters}m</span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>{t("availableSeats")}</span>
          <span className={`font-medium ${noSeats ? "text-content-destructive" : "text-content-primary"}`}>
            {noSeats ? t("full") : ride.available_seats}
          </span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>{t("basePrice")}</span>
          <span className="font-medium text-content-primary">{formatCurrency(Number(ride.per_seat_price), locale)}</span>
        </div>
      </div>

      {/* Premium options */}
      {hasPremium && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-content-primary">{t("pickupDropoffOption")}</p>

          <button
            type="button"
            onClick={() => setPremiumOption("standard")}
            className={`w-full flex items-center justify-between p-3 rounded-xl border text-sm transition-colors ${
              premiumOption === "standard"
                ? "border-brand-primary bg-brand-primary/5"
                : "border-border-default bg-surface-card"
            }`}
          >
            <span className="font-medium text-content-primary">{t("standard")}</span>
            <span className="text-content-muted">{formatCurrency(Number(ride.per_seat_price), locale)}</span>
          </button>

          {ctx.premium_pickup_available && (
            <button
              type="button"
              onClick={() => setPremiumOption(
                premiumOption === "standard"        ? "premium_pickup" :
                premiumOption === "premium_pickup"  ? "standard" :
                premiumOption === "premium_dropoff" ? "premium_both" :
                /* premium_both */                    "premium_dropoff"
              )}
              className={`w-full flex items-center justify-between p-3 rounded-xl border text-sm transition-colors ${
                premiumOption === "premium_pickup" || premiumOption === "premium_both"
                  ? "border-amber-400 bg-amber-50"
                  : "border-border-default bg-surface-card"
              }`}
            >
              <span className="font-medium text-amber-700">Premium Pickup</span>
              <span className="text-amber-600">+{formatCurrency(ctx.premium_pickup_fee ?? 0, locale)}</span>
            </button>
          )}

          {ctx.premium_dropoff_available && (
            <button
              type="button"
              onClick={() => setPremiumOption(
                premiumOption === "standard"        ? "premium_dropoff" :
                premiumOption === "premium_dropoff" ? "standard" :
                premiumOption === "premium_pickup"  ? "premium_both" :
                /* premium_both */                    "premium_pickup"
              )}
              className={`w-full flex items-center justify-between p-3 rounded-xl border text-sm transition-colors ${
                premiumOption === "premium_dropoff" || premiumOption === "premium_both"
                  ? "border-amber-400 bg-amber-50"
                  : "border-border-default bg-surface-card"
              }`}
            >
              <span className="font-medium text-amber-700">Premium Dropoff</span>
              <span className="text-amber-600">+{formatCurrency(ctx.premium_dropoff_fee ?? 0, locale)}</span>
            </button>
          )}
        </div>
      )}

      {/* Price summary + Book button */}
      <div className="space-y-3 pt-2 border-t border-border-default">
        {!detail.existing_booking && !noSeats && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-content-secondary">
              {ride.recurring_ride_definition_id
                ? t("numberOfSeatsForDay", { day: formatDayLabel(ride.departure_datetime, locale) })
                : t("numberOfSeats")}
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setSeatCount((n) => Math.max(1, n - 1))}
                disabled={clampedSeatCount <= 1}
                className="w-8 h-8 rounded-full border border-border-default text-content-primary disabled:opacity-40 hover:bg-surface-bg transition-colors"
              >
                −
              </button>
              <span className="w-6 text-center font-semibold text-content-primary">{clampedSeatCount}</span>
              <button
                type="button"
                onClick={() => setSeatCount((n) => Math.min(maxSeats, n + 1))}
                disabled={clampedSeatCount >= maxSeats}
                className="w-8 h-8 rounded-full border border-border-default text-content-primary disabled:opacity-40 hover:bg-surface-bg transition-colors"
              >
                +
              </button>
            </div>
          </div>
        )}

        <div className="flex justify-between text-sm font-semibold text-content-primary">
          <span>{t("total")}</span>
          <span>{formatCurrency(Number(totalPrice), locale)}</span>
        </div>

        {detail.existing_booking ? (
          <div className="space-y-2 p-4 rounded-xl bg-surface-bg border border-border-default">
            <p className="text-sm font-medium text-content-primary">{t("existingBookingTitle")}</p>
            <p className="text-xs text-content-muted">{t("existingBookingBody")}</p>
            <Link
              href={`/bookings/${detail.existing_booking.booking_id}`}
              className="block w-full text-center bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
            >
              {t("manageBooking")}
            </Link>
          </div>
        ) : (
          <button
            type="button"
            disabled={noSeats}
            onClick={handleBook}
            className="w-full bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-opacity"
          >
            {noSeats ? t("noSeatsAvailable") : t("bookSeat")}
          </button>
        )}
      </div>

      {/* Booking confirmation bottom sheet */}
      <BottomSheet isOpen={showSheet} onClose={() => { setShowSheet(false); setBookingError(null); }}>
        <div className="space-y-4 pt-1">
          <h2 className="text-base font-semibold text-content-primary">{t("confirmBooking")}</h2>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-content-secondary">
              <span>{t("driver")}</span>
              <span className="font-medium text-content-primary">{ride.driver.display_name ?? "—"}</span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>{t("departure")}</span>
              <span className="font-medium text-content-primary">{formatDeparture(ride.departure_datetime, locale)}</span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>{t("pickup")}</span>
              <span className="font-medium text-content-primary">
                {t("pickupWalkNote", { meters: ctx.pickup_walk_meters })}
              </span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>{t("dropoff")}</span>
              <span className="font-medium text-content-primary">
                {t("dropoffWalkNote", { meters: ctx.dropoff_walk_meters })}
              </span>
            </div>
          </div>

          <div className="border-t border-border-default pt-3 space-y-1 text-sm">
            <div className="flex justify-between text-content-secondary">
              <span>{formatDayLabel(ride.departure_datetime, locale)}</span>
              <span className="font-medium text-content-primary">
                {t("seatsCount", { count: clampedSeatCount })} · {formatCurrency(Number(ride.per_seat_price) * clampedSeatCount + premiumFee, locale)}
              </span>
            </div>
            {selectedExtraCount > 0 &&
              Object.entries(extraSeats).map(([rideId, seats]) => {
                const inst = siblingInstances.find((i) => i.ride_id === rideId);
                if (!inst) return null;
                return (
                  <div key={rideId} className="flex justify-between text-content-secondary">
                    <span>{formatDayLabel(inst.departure_datetime, locale)}</span>
                    <span className="font-medium text-content-primary">
                      {t("seatsCount", { count: seats })} · {formatCurrency(parseFloat(inst.per_seat_price) * seats + premiumFee, locale)}
                    </span>
                  </div>
                );
              })}
            {premiumFee > 0 && (
              <p className="text-xs text-amber-700">{t("premiumFeeIncludedNote")}</p>
            )}
            {clampedPointsToRedeem > 0 && (
              <div className="flex justify-between text-content-secondary">
                <span>{t("payWithPoints.discountLineLabel")}</span>
                <span className="font-medium text-green-600">
                  −{formatCurrency(clampedPointsToRedeem, locale)}
                </span>
              </div>
            )}
            <div className="flex justify-between font-semibold text-content-primary pt-1 border-t border-border-default">
              <span>{t("total")}</span>
              <span>{formatCurrency(Number(totalPrice), locale)}</span>
            </div>
          </div>

          {!ride.is_sponsored && selectedExtraCount > 0 && (
            <p className="text-xs text-content-muted border-t border-border-default pt-3">
              {t("loyaltyRedemption.notAvailableForMultiDay")}
            </p>
          )}

          {pointsRedemptionAvailable && maxPointsRedeemable > 0 && (
            <div className="border-t border-border-default pt-3 space-y-2">
              <p className="text-sm font-medium text-content-primary">
                {t("payWithPoints.heading")}
              </p>
              <p className="text-xs text-content-muted">
                {t("payWithPoints.subtitle", { max: maxPointsRedeemable })}
              </p>
              <div className="rounded-xl border border-border-default bg-surface-card p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-content-primary">
                    {t("payWithPoints.pointsAndDiscount", {
                      points: clampedPointsToRedeem,
                      discount: formatCurrency(clampedPointsToRedeem, locale),
                    })}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={maxPointsRedeemable}
                  step={1}
                  value={clampedPointsToRedeem}
                  onChange={(e) => setPointsToRedeem(Number(e.target.value))}
                  className="w-full accent-brand-primary"
                  aria-label={t("payWithPoints.heading")}
                />
                <div className="flex items-center justify-between text-xs text-content-muted">
                  <span>0</span>
                  <span>{maxPointsRedeemable}</span>
                </div>
              </div>
            </div>
          )}

          {bookingError && (
            <p className="text-sm text-content-destructive">{bookingError}</p>
          )}

          <button
            type="button"
            onClick={confirmBooking}
            disabled={bookingLoading}
            className="w-full flex items-center justify-center gap-2 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-opacity"
          >
            {bookingLoading && <Spinner />}
            {bookingLoading ? t("booking") : t("confirmBooking")}
          </button>
        </div>
      </BottomSheet>

      <VerificationRequiredModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        role="passenger"
      />
    </div>
  );
}
