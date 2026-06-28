"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { BookingStatusBadge } from "@/components/bookings/BookingStatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { useBookingStatus } from "@/lib/hooks/useBookingStatus";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface BookingDetail {
  booking_id: string;
  ride_id: string;
  status: BookingStatus;
  driver_display_name?: string;
  driver_avatar_url?: string;
  departure_datetime?: string;
  per_seat_price: string;
  total_price: string;
  premium_pickup_requested: boolean;
  premium_dropoff_requested: boolean;
  premium_pickup_fee?: string | null;
  premium_dropoff_fee?: string | null;
  boarding_point: { lat: number; lng: number };
  alighting_point: { lat: number; lng: number };
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

function formatDateTime(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=16`,
      { headers: { "Accept-Language": "en" } },
    );
    if (!res.ok) return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    const data = await res.json();
    const a = data.address ?? {};
    const parts = [a.road, a.suburb ?? a.city_district, a.city ?? a.town].filter(Boolean);
    return parts.length ? parts.join(", ") : (data.display_name ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
  } catch {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }
}

export default function PassengerBookingDetailPage() {
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
      setError(e instanceof Error ? e.message : "Failed to load booking");
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
      alert(e instanceof Error ? e.message : "Failed to cancel booking");
    } finally {
      setCancelling(false);
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
        <p>{error ?? "Booking not found"}</p>
        <button className="mt-2 text-sm underline text-brand-primary" onClick={fetchBooking}>
          Try again
        </button>
      </div>
    );
  }

  const isCancellable =
    booking.status === "pending" || booking.status === "confirmed";

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          ←
        </button>
        <h1 className="text-xl font-semibold text-content-primary">Booking Details</h1>
        <BookingStatusBadge status={booking.status} />
      </div>

      {/* Driver & departure */}
      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-3">
            {booking.driver_avatar_url ? (
              <img
                src={booking.driver_avatar_url}
                alt={booking.driver_display_name ?? "Driver"}
                className="h-10 w-10 rounded-full object-cover shrink-0"
              />
            ) : (
              <div className="h-10 w-10 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-sm font-medium text-content-secondary">
                {(booking.driver_display_name ?? "D")[0].toUpperCase()}
              </div>
            )}
            <div>
              <p className="font-medium text-content-primary">{booking.driver_display_name ?? "Driver"}</p>
              <p className="text-xs text-content-muted">Driver</p>
            </div>
          </div>
          <div>
            <p className="text-xs text-content-muted">Departure</p>
            <p className="text-sm font-medium text-content-primary">{formatDateTime(booking.departure_datetime)}</p>
          </div>
        </div>
      </div>

      {/* Route points */}
      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-3">
          <div>
            <p className="text-xs text-content-muted uppercase tracking-wide">Boarding point</p>
            <p className="text-sm font-medium text-content-primary">
              {boardingAddress ?? "Loading…"}
            </p>
          </div>
          <div className="border-t border-border-default" />
          <div>
            <p className="text-xs text-content-muted uppercase tracking-wide">Alighting point</p>
            <p className="text-sm font-medium text-content-primary">
              {alightingAddress ?? "Loading…"}
            </p>
          </div>
        </div>
      </div>

      {/* Price breakdown */}
      <div className="rounded-xl border border-border-default bg-surface-card">
        <div className="p-4 space-y-2">
          <p className="text-sm font-medium text-content-primary">Price Breakdown</p>
          <div className="flex justify-between text-sm">
            <span className="text-content-muted">Base fare</span>
            <span className="text-content-primary">EGP {booking.per_seat_price}</span>
          </div>
          {booking.premium_pickup_requested && booking.premium_pickup_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-content-muted">Premium pickup</span>
              <span className="text-content-primary">EGP {booking.premium_pickup_fee}</span>
            </div>
          )}
          {booking.premium_dropoff_requested && booking.premium_dropoff_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-content-muted">Premium dropoff</span>
              <span className="text-content-primary">EGP {booking.premium_dropoff_fee}</span>
            </div>
          )}
          <div className="border-t border-border-default pt-2 flex justify-between font-semibold text-content-primary">
            <span>Total</span>
            <span>EGP {booking.total_price}</span>
          </div>
        </div>
      </div>

      {/* Cancellation info */}
      {booking.status === "cancelled" && (
        <div className="rounded-xl border border-red-100 bg-red-50">
          <div className="p-4 space-y-1">
            <p className="text-sm font-medium text-red-700">Booking Cancelled</p>
            {booking.cancellation_reason && (
              <p className="text-xs text-red-600">{booking.cancellation_reason}</p>
            )}
            {booking.cancelled_at && (
              <p className="text-xs text-red-500">{formatDateTime(booking.cancelled_at)}</p>
            )}
            {booking.late_cancellation && (
              <p className="text-xs text-amber-600 font-medium">Late cancellation recorded</p>
            )}
          </div>
        </div>
      )}

      {/* Cancel action */}
      {isCancellable && !showConfirm && (
        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          className="w-full rounded-xl border border-red-200 text-red-600 hover:bg-red-50 px-4 py-2.5 text-sm font-medium transition-colors"
        >
          Cancel Booking
        </button>
      )}

      {showConfirm && (
        <div className="rounded-xl border border-red-200 bg-surface-card">
          <div className="p-4 space-y-3">
            <p className="text-sm font-medium text-content-primary">Are you sure you want to cancel?</p>
            <p className="text-xs text-content-muted">
              This action cannot be undone. Your seat will be released.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {cancelling && <Spinner />}
                {cancelling ? "Cancelling…" : "Yes, Cancel"}
              </button>
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                disabled={cancelling}
                className="flex-1 rounded-xl border border-border-default text-content-primary hover:bg-surface-bg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
              >
                Keep Booking
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
