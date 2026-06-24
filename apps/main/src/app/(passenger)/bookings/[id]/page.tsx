"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { BookingStatusBadge } from "@/components/bookings/BookingStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

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

function formatCoord(pt: { lat: number; lng: number }) {
  return `${pt.lat.toFixed(5)}, ${pt.lng.toFixed(5)}`;
}

export default function PassengerBookingDetailPage() {
  const params = useParams<{ id: string }>();
  const bookingId = params.id;

  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchBooking = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch(`/api/v1/bookings/${bookingId}`);
      setBooking(data);
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
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="p-4 text-center text-destructive">
        <p>{error ?? "Booking not found"}</p>
        <button className="mt-2 text-sm underline" onClick={fetchBooking}>
          Try again
        </button>
      </div>
    );
  }

  const isCancellable =
    booking.status === "pending" || booking.status === "confirmed";

  const hasPremium =
    booking.premium_pickup_requested || booking.premium_dropoff_requested;

  return (
    <div className="max-w-md mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Booking Details</h1>
        <BookingStatusBadge status={booking.status} />
      </div>

      {/* Driver & departure */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center gap-3">
            {booking.driver_avatar_url ? (
              <img
                src={booking.driver_avatar_url}
                alt={booking.driver_display_name ?? "Driver"}
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : (
              <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
                {(booking.driver_display_name ?? "D")[0].toUpperCase()}
              </div>
            )}
            <div>
              <p className="font-medium">{booking.driver_display_name ?? "Driver"}</p>
              <p className="text-xs text-muted-foreground">Driver</p>
            </div>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Departure</p>
            <p className="text-sm font-medium">{formatDateTime(booking.departure_datetime)}</p>
          </div>
        </CardContent>
      </Card>

      {/* Route points */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Boarding point</p>
            <p className="text-sm font-mono">{formatCoord(booking.boarding_point)}</p>
          </div>
          <div className="border-t" />
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Alighting point</p>
            <p className="text-sm font-mono">{formatCoord(booking.alighting_point)}</p>
          </div>
        </CardContent>
      </Card>

      {/* Price breakdown */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <p className="text-sm font-medium">Price Breakdown</p>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Base fare</span>
            <span>EGP {booking.per_seat_price}</span>
          </div>
          {booking.premium_pickup_requested && booking.premium_pickup_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Premium pickup</span>
              <span>EGP {booking.premium_pickup_fee}</span>
            </div>
          )}
          {booking.premium_dropoff_requested && booking.premium_dropoff_fee && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Premium dropoff</span>
              <span>EGP {booking.premium_dropoff_fee}</span>
            </div>
          )}
          <div className="border-t pt-2 flex justify-between font-semibold">
            <span>Total</span>
            <span>EGP {booking.total_price}</span>
          </div>
        </CardContent>
      </Card>

      {/* Cancellation info */}
      {booking.status === "cancelled" && (
        <Card className="border-red-100 bg-red-50">
          <CardContent className="p-4 space-y-1">
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
          </CardContent>
        </Card>
      )}

      {/* Cancel action */}
      {isCancellable && !showConfirm && (
        <Button
          variant="outline"
          className="w-full border-red-200 text-red-600 hover:bg-red-50"
          onClick={() => setShowConfirm(true)}
        >
          Cancel Booking
        </Button>
      )}

      {showConfirm && (
        <Card className="border-red-200">
          <CardContent className="p-4 space-y-3">
            <p className="text-sm font-medium">Are you sure you want to cancel?</p>
            <p className="text-xs text-muted-foreground">
              This action cannot be undone. Your seat will be released.
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                className="flex-1"
                onClick={handleCancel}
                disabled={cancelling}
              >
                {cancelling ? "Cancelling…" : "Yes, Cancel"}
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowConfirm(false)}
                disabled={cancelling}
              >
                Keep Booking
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
