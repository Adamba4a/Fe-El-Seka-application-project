"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { BookingCard } from "@/components/bookings/BookingCard";
import { createClient } from "@/lib/supabase/client";
import { useBookingStatus } from "@/lib/hooks/useBookingStatus";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface DriverBooking {
  booking_id: string;
  status: BookingStatus;
  passenger: { display_name?: string; avatar_url?: string };
  per_seat_price: string;
  total_price: string;
  boarding_point: { lat: number; lng: number };
  alighting_point: { lat: number; lng: number };
  premium_pickup_requested?: boolean;
  premium_pickup_fee?: string | null;
  premium_dropoff_requested?: boolean;
  premium_dropoff_fee?: string | null;
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
    // FastAPI wraps errors as { detail: { message: "..." } } or { detail: "string" }
    const msg =
      err?.detail?.message ?? err?.detail ?? err?.message ?? `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}

export default function DriverRideBookingsPage() {
  const params = useParams<{ id: string }>();
  const rideId = params.id;
  const router = useRouter();

  const [bookings, setBookings] = useState<DriverBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchBookings = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch(`/api/v1/rides/${rideId}/bookings`);
      setBookings(data.bookings ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load bookings");
    } finally {
      setLoading(false);
    }
  }, [rideId]);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const { lastEvent } = useBookingStatus({ rideId });

  // New booking INSERT: re-fetch the list to get full passenger details
  // (Realtime payload carries PostGIS binary for pickup/dropoff points, not lat/lng floats)
  useEffect(() => {
    if (!lastEvent || lastEvent.eventType !== "INSERT") return;
    fetchBookings();
  }, [lastEvent, fetchBookings]);

  async function handleConfirm(bookingId: string) {
    setActionLoading(bookingId);
    try {
      await apiFetch(`/api/v1/rides/${rideId}/bookings/${bookingId}/confirm`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setBookings((prev) =>
        prev.map((b) =>
          b.booking_id === bookingId ? { ...b, status: "confirmed" } : b
        )
      );
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to confirm booking");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(bookingId: string) {
    const promptResult = window.prompt("Reason for rejection (optional):");
    const reason = promptResult ?? undefined;
    setActionLoading(bookingId);
    try {
      const result = await apiFetch(
        `/api/v1/rides/${rideId}/bookings/${bookingId}/reject`,
        {
          method: "POST",
          body: JSON.stringify({ reason: reason ?? null }),
        }
      );
      if (result.fallback_applied) {
        // Premium pickup declined but booking kept as confirmed; subtract pickup fee from total
        setBookings((prev) =>
          prev.map((b) =>
            b.booking_id === bookingId
              ? {
                  ...b,
                  status: "confirmed",
                  premium_pickup_requested: false,
                  premium_pickup_fee: null,
                  total_price: (
                    Number(b.total_price) - Number(b.premium_pickup_fee || 0)
                  ).toFixed(2),
                }
              : b
          )
        );
      } else {
        setBookings((prev) =>
          prev.map((b) =>
            b.booking_id === bookingId ? { ...b, status: "cancelled" } : b
          )
        );
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to reject booking");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCancel(bookingId: string) {
    const promptResult = window.prompt("Reason for cancellation (optional):");
    if (promptResult === null) return; // user dismissed dialog
    setActionLoading(bookingId);
    try {
      await apiFetch(
        `/api/v1/rides/${rideId}/bookings/${bookingId}/cancel`,
        {
          method: "POST",
          body: JSON.stringify({ reason: promptResult || null }),
        }
      );
      setBookings((prev) =>
        prev.map((b) =>
          b.booking_id === bookingId ? { ...b, status: "cancelled" } : b
        )
      );
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to cancel booking");
    } finally {
      setActionLoading(null);
    }
  }

  const pending = bookings.filter((b) => b.status === "pending");
  const confirmed = bookings.filter((b) => b.status === "confirmed");

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-destructive">
        <p>{error}</p>
        <button
          className="mt-2 text-sm underline"
          onClick={fetchBookings}
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto p-4 space-y-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          ←
        </button>
        <h1 className="text-xl font-semibold">Booking Requests</h1>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Pending Requests ({pending.length})
        </h2>
        {pending.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No pending booking requests
          </p>
        ) : (
          pending.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              variant="driver"
              booking={booking}
              onConfirm={() => handleConfirm(booking.booking_id)}
              onReject={() => handleReject(booking.booking_id)}
              actionLoading={actionLoading === booking.booking_id}
            />
          ))
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Confirmed Passengers ({confirmed.length})
        </h2>
        {confirmed.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No confirmed passengers yet
          </p>
        ) : (
          confirmed.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              variant="driver"
              booking={booking}
              cancelAvailable={true}
              onCancel={() => handleCancel(booking.booking_id)}
              actionLoading={actionLoading === booking.booking_id}
            />
          ))
        )}
      </section>
    </div>
  );
}
