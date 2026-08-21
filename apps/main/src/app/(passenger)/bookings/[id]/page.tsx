"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { BookingStatusBadge } from "@/components/bookings/BookingStatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { useBookingStatus } from "@/lib/hooks/useBookingStatus";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Locale } from "@fe-el-seka/shared";

const RideDetailMap = dynamic(
  () => import("@/components/bookings/RideDetailMap").then((m) => ({ default: m.RideDetailMap })),
  { ssr: false, loading: () => <div className="w-full h-56 bg-surface-bg rounded-xl animate-pulse" /> }
);

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface BookingDetail {
  booking_id: string;
  ride_id: string;
  status: BookingStatus;
  driver_id: string;
  driver_display_name?: string;
  driver_avatar_url?: string;
  departure_datetime?: string;
  per_seat_price: string;
  total_price: string;
  seats: number;
  available_seats: number;
  premium_pickup_requested: boolean;
  premium_dropoff_requested: boolean;
  premium_pickup_fee?: string | null;
  premium_dropoff_fee?: string | null;
  boarding_point: { lat: number; lng: number };
  alighting_point: { lat: number; lng: number };
  route_geometry: object | null;
  cancellation_reason?: string | null;
  late_cancellation: boolean;
  created_at: string;
  confirmed_at?: string | null;
  cancelled_at?: string | null;
}

async function apiFetch(path: string, options?: RequestInit) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg =
      err?.detail?.message ?? err?.detail ?? err?.message ?? `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}

function formatDateTime(iso: string | null | undefined, locale: Locale) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch(
      `${base}/api/geocode/reverse?lat=${lat}&lng=${lng}`,
      { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal },
    );
    if (!res.ok) return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    const data = await res.json();
    const a = data.address_parts ?? {};
    const parts = [a.road, a.suburb ?? a.city_district, a.city ?? a.town].filter(Boolean);
    return parts.length ? parts.join(", ") : (data.address ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
  } catch {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  } finally {
    clearTimeout(timer);
  }
}

export default function PassengerBookingDetailPage() {
  const t = useTranslations("passenger.bookingDetail");
  const tBookings = useTranslations("passenger.bookings");
  const locale = useLocale() as Locale;
  const params = useParams<{ id: string }>();
  const bookingId = params.id;
  const router = useRouter();

  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [boardingAddress, setBoardingAddress] = useState<string | null>(null);
  const [alightingAddress, setAlightingAddress] = useState<string | null>(null);
  const [showAddSeats, setShowAddSeats] = useState(false);
  const [addSeatsCount, setAddSeatsCount] = useState(1);
  const [addingSeats, setAddingSeats] = useState(false);
  const [addSeatsError, setAddSeatsError] = useState<string | null>(null);

  const { lastEvent } = useBookingStatus({ bookingId });

  // Apply real-time status changes without a full refetch
  useEffect(() => {
    if (!lastEvent || lastEvent.eventType !== "UPDATE") return;
    const updated = lastEvent.new as {
      status?: BookingStatus;
      cancelled_at?: string | null;
      cancellation_reason?: string | null;
    };
    if (!updated?.status) return;
    setBooking((prev) =>
      prev
        ? {
            ...prev,
            status: updated.status!,
            cancelled_at: updated.cancelled_at ?? prev.cancelled_at,
            cancellation_reason: updated.cancellation_reason ?? prev.cancellation_reason,
          }
        : prev
    );
    // Close the confirm dialog if the booking was externally cancelled (e.g. driver)
    if (updated.status === "cancelled") setShowConfirm(false);
  }, [lastEvent]);

  const fetchBooking = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch(`/api/v1/bookings/${bookingId}`);
      setBooking(data);
      // Reverse-geocode boarding and alighting points in parallel
      const [boarding, alighting] = await Promise.all([
        reverseGeocode(data.boarding_point.lat, data.boarding_point.lng),
        reverseGeocode(data.alighting_point.lat, data.alighting_point.lng),
      ]);
      setBoardingAddress(boarding);
      setAlightingAddress(alighting);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [bookingId]);

  useEffect(() => {
    fetchBooking();
  }, [fetchBooking]);

  async function handleCancel() {
    if (!booking) return;
    setCancelling(true);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingId}/cancel`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setBooking((prev) =>
        prev
          ? {
              ...prev,
              status: res.status,
              cancelled_at: res.cancelled_at,
              late_cancellation: res.late_cancellation,
            }
          : prev
      );
      setShowConfirm(false);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t("errors.cancelFailed"));
    } finally {
      setCancelling(false);
    }
  }

  async function handleAddSeats() {
    if (!booking) return;
    setAddingSeats(true);
    setAddSeatsError(null);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingId}/seats`, {
        method: "POST",
        body: JSON.stringify({ seats: addSeatsCount }),
      });
      setBooking((prev) =>
        prev
          ? {
              ...prev,
              seats: res.seats,
              total_price: res.total_price,
              available_seats: Math.max(prev.available_seats - addSeatsCount, 0),
            }
          : prev
      );
      setShowAddSeats(false);
      setAddSeatsCount(1);
    } catch (e: unknown) {
      setAddSeatsError(e instanceof Error ? e.message : t("errors.addSeatsFailed"));
    } finally {
      setAddingSeats(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("bookingNotFound")}</p>
        <button className="mt-2 text-sm underline text-brand-primary" onClick={fetchBooking}>
          {tBookings("tryAgain")}
        </button>
      </div>
    );
  }

  const isCancellable =
    booking.status === "pending" || booking.status === "confirmed";

  return (
    <div className="max-w-md mx-auto space-y-4 py-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-dash-navy hover:opacity-70"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-xl font-bold text-dash-navy flex-1">{t("title")}</h1>
        <BookingStatusBadge status={booking.status} />
      </div>

      {/* Driver & departure */}
      <div className="rounded-2xl bg-dash-surface shadow-sm">
        <div className="p-5 space-y-3">
          <div className="flex items-center gap-3">
            {booking.driver_avatar_url ? (
              <img
                src={booking.driver_avatar_url}
                alt={booking.driver_display_name ?? t("driverLabel")}
                className="h-12 w-12 rounded-full object-cover shrink-0"
              />
            ) : (
              <div className="h-12 w-12 rounded-full bg-dash-bg flex items-center justify-center shrink-0 text-sm font-semibold text-dash-navy">
                {(booking.driver_display_name ?? "D")[0].toUpperCase()}
              </div>
            )}
            <div>
              <p className="font-bold text-dash-navy">{booking.driver_display_name ?? t("driverLabel")}</p>
              <p className="text-xs text-dash-text-muted">{t("driverLabel")}</p>
            </div>
          </div>
          <div className="h-px bg-dash-border" />
          <div>
            <p className="text-xs text-dash-text-muted">{t("departure")}</p>
            <p className="text-sm font-medium text-dash-navy">{formatDateTime(booking.departure_datetime, locale)}</p>
          </div>
          {(booking.status === "confirmed" || booking.status === "completed") && (
            <Link
              href={`/users/${booking.driver_id}`}
              className="block w-full text-center rounded-xl bg-dash-primary px-4 py-2 text-sm font-semibold text-content-inverse hover:opacity-90 transition-opacity"
            >
              {t("viewProfile")}
            </Link>
          )}
        </div>
      </div>

      {/* Route map */}
      <RideDetailMap
        routeGeometry={booking.route_geometry}
        boardingPoint={booking.boarding_point}
        alightingPoint={booking.alighting_point}
        origin={booking.boarding_point}
        destination={booking.alighting_point}
      />

      {/* Route points */}
      <div className="rounded-2xl bg-dash-surface shadow-sm">
        <div className="p-5 space-y-3">
          <div>
            <p className="text-xs text-dash-text-muted uppercase tracking-wide">{t("boardingPoint")}</p>
            <p className="text-sm font-medium text-dash-navy">
              {boardingAddress ?? t("loadingLocation")}
            </p>
          </div>
          <div className="border-t border-dash-border" />
          <div>
            <p className="text-xs text-dash-text-muted uppercase tracking-wide">{t("alightingPoint")}</p>
            <p className="text-sm font-medium text-dash-navy">
              {alightingAddress ?? t("loadingLocation")}
            </p>
          </div>
        </div>
      </div>

      {/* Live tracking — shown once driver has accepted and ride may be in progress */}
      {booking.status === "confirmed" && (
        <Link
          href={`/rides/${booking.ride_id}/tracking`}
          className="flex items-center justify-center gap-2 w-full rounded-2xl bg-dash-primary hover:opacity-90 text-white px-4 py-3.5 text-sm font-semibold transition-opacity"
        >
          <span>📍</span>
          {t("trackLive")}
        </Link>
      )}

      {/* Rate & report — available once the ride is completed */}
      {booking.status === "completed" && (
        <Link
          href={`/ratings/${booking.booking_id}`}
          className="flex items-center justify-center gap-2 w-full rounded-2xl bg-dash-primary hover:opacity-90 text-white px-4 py-3.5 text-sm font-semibold transition-opacity"
        >
          <span>⭐</span>
          {t("rateAndReport")}
        </Link>
      )}

      {/* Price breakdown */}
      <div className="rounded-2xl bg-dash-surface shadow-sm">
        <div className="p-5 space-y-2">
          <p className="text-sm font-bold text-dash-navy">{t("priceBreakdown")}</p>
          {booking.seats > 1 && (
            <div className="flex justify-between text-sm">
              <span className="text-dash-text-muted">{t("seats")}</span>
              <span className="text-dash-navy">{booking.seats}</span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-dash-text-muted">{t("baseFare")}</span>
            <span className="text-dash-navy">{formatCurrency(Number(booking.per_seat_price) * booking.seats, locale)}</span>
          </div>
          {booking.premium_pickup_requested && booking.premium_pickup_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-dash-text-muted">{t("premiumPickup")}</span>
              <span className="text-dash-navy">{formatCurrency(Number(booking.premium_pickup_fee), locale)}</span>
            </div>
          )}
          {booking.premium_dropoff_requested && booking.premium_dropoff_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-dash-text-muted">{t("premiumDropoff")}</span>
              <span className="text-dash-navy">{formatCurrency(Number(booking.premium_dropoff_fee), locale)}</span>
            </div>
          )}
          <div className="border-t border-dash-border pt-2 flex justify-between font-bold text-dash-navy">
            <span>{t("total")}</span>
            <span>{formatCurrency(Number(booking.total_price), locale)}</span>
          </div>
        </div>
      </div>

      {/* Add seats */}
      {isCancellable && booking.available_seats > 0 && !showAddSeats && (
        <button
          type="button"
          onClick={() => { setAddSeatsCount(1); setAddSeatsError(null); setShowAddSeats(true); }}
          className="w-full rounded-2xl border border-dash-border bg-dash-surface text-dash-primary hover:bg-dash-bg px-4 py-3 text-sm font-semibold transition-colors"
        >
          {t("addSeats")}
        </button>
      )}

      {showAddSeats && (
        <div className="rounded-2xl border border-dash-border bg-dash-surface shadow-sm">
          <div className="p-5 space-y-3">
            <p className="text-sm font-bold text-dash-navy">{t("addSeats")}</p>
            <p className="text-xs text-dash-text-muted">{t("addSeatsBody")}</p>

            <div className="flex items-center justify-center gap-4">
              <button
                type="button"
                onClick={() => setAddSeatsCount((n) => Math.max(1, n - 1))}
                disabled={addSeatsCount <= 1}
                className="w-8 h-8 rounded-full border border-dash-border text-dash-navy disabled:opacity-40 hover:bg-dash-bg transition-colors"
              >
                −
              </button>
              <span className="w-6 text-center font-semibold text-dash-navy">{addSeatsCount}</span>
              <button
                type="button"
                onClick={() => setAddSeatsCount((n) => Math.min(booking.available_seats, 8, n + 1))}
                disabled={addSeatsCount >= Math.min(booking.available_seats, 8)}
                className="w-8 h-8 rounded-full border border-dash-border text-dash-navy disabled:opacity-40 hover:bg-dash-bg transition-colors"
              >
                +
              </button>
            </div>

            {addSeatsError && <p className="text-xs text-content-destructive text-center">{addSeatsError}</p>}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleAddSeats}
                disabled={addingSeats}
                className="flex-1 rounded-xl bg-dash-primary text-content-inverse px-4 py-2.5 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {addingSeats && <Spinner />}
                {addingSeats
                  ? t("addingSeats")
                  : addSeatsCount === 1
                    ? t("addSeatsSubmitOne")
                    : t("addSeatsSubmit", { count: addSeatsCount })}
              </button>
              <button
                type="button"
                onClick={() => setShowAddSeats(false)}
                disabled={addingSeats}
                className="flex-1 rounded-xl border border-dash-border text-dash-navy hover:bg-dash-bg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {t("keepBooking")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancellation info */}
      {booking.status === "cancelled" && (
        <div className="rounded-2xl border border-red-100 bg-red-50">
          <div className="p-5 space-y-1">
            <p className="text-sm font-medium text-red-700">{t("bookingCancelledTitle")}</p>
            {booking.cancellation_reason && (
              <p className="text-xs text-red-600">{booking.cancellation_reason}</p>
            )}
            {booking.cancelled_at && (
              <p className="text-xs text-red-500">{formatDateTime(booking.cancelled_at, locale)}</p>
            )}
            {booking.late_cancellation && (
              <p className="text-xs text-amber-600 font-medium">{t("lateCancellation")}</p>
            )}
          </div>
        </div>
      )}

      {/* Cancel action */}
      {isCancellable && !showConfirm && (
        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          className="w-full rounded-2xl border border-dash-border bg-dash-surface text-content-destructive hover:bg-status-cancelled-bg px-4 py-3 text-sm font-semibold transition-colors"
        >
          {t("cancelBooking")}
        </button>
      )}

      {showConfirm && (
        <div className="rounded-2xl border border-red-200 bg-dash-surface shadow-sm">
          <div className="p-5 space-y-3">
            <p className="text-sm font-bold text-dash-navy">{t("cancelConfirmTitle")}</p>
            <p className="text-xs text-dash-text-muted">
              {t("cancelConfirmBody")}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="flex-1 rounded-xl bg-surface-destructive text-content-inverse px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {cancelling && <Spinner />}
                {cancelling ? t("cancelling") : t("yesCancel")}
              </button>
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                disabled={cancelling}
                className="flex-1 rounded-xl border border-dash-border text-dash-navy hover:bg-dash-bg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {t("keepBooking")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
