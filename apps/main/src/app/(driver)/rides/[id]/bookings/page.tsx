"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { BookingCard } from "@/components/bookings/BookingCard";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { VerificationRequiredModal } from "@/components/verification/VerificationRequiredModal";
import { createClient } from "@/lib/supabase/client";
import { getRide } from "@/lib/api/rides";
import { useBookingStatus } from "@/lib/hooks/useBookingStatus";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Ride, Locale } from "@fe-el-seka/shared";

const RideDetailMap = dynamic(
  () => import("@/components/bookings/RideDetailMap").then((m) => ({ default: m.RideDetailMap })),
  { ssr: false, loading: () => <div className="w-full h-56 bg-surface-bg rounded-xl animate-pulse" /> }
);

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface DriverBooking {
  booking_id: string;
  passenger_id: string;
  status: BookingStatus;
  passenger: {
    display_name?: string;
    avatar_url?: string;
    rating_avg?: number | null;
    rating_count?: number;
  };
  per_seat_price: string;
  total_price: string;
  seats: number;
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
    const body = await res.json().catch(() => ({}));
    // FastAPI wraps errors as { detail: { error, message } } or { detail: "string" }
    const detail =
      body?.detail && typeof body.detail === "object" ? body.detail : body;
    const msg =
      detail?.message ?? (typeof body?.detail === "string" ? body.detail : undefined) ?? `HTTP ${res.status}`;
    throw { error: detail?.error, message: msg };
  }
  return res.json();
}

export default function DriverRideBookingsPage() {
  const t = useTranslations("driver.bookings");
  const tNav = useTranslations("nav");
  const locale = useLocale() as Locale;
  const params = useParams<{ id: string }>();
  const rideId = params.id;
  const router = useRouter();

  const [bookings, setBookings] = useState<DriverBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [ride, setRide] = useState<Ride | null>(null);
  const [mapBooking, setMapBooking] = useState<DriverBooking | null>(null);
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);

  useEffect(() => {
    (async () => {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      try {
        const detail = await getRide(session.access_token, rideId);
        setRide(detail.ride);
      } catch {
        // Map view falls back to hidden if the ride can't be loaded
      }
    })();
  }, [rideId]);

  const fetchBookings = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch(`/api/v1/rides/${rideId}/bookings`);
      setBookings(data.bookings ?? []);
    } catch (e: any) {
      setError(e?.message ?? t("loadFailed"));
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
    } catch (e: any) {
      if (e?.error === "verification_required") {
        setVerifyModalOpen(true);
      } else {
        alert(e?.message ?? t("confirmFailed"));
      }
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(bookingId: string) {
    const promptResult = window.prompt(t("rejectReasonPrompt"));
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
    } catch (e: any) {
      if (e?.error === "verification_required") {
        setVerifyModalOpen(true);
      } else {
        alert(e?.message ?? t("rejectFailed"));
      }
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCancel(bookingId: string) {
    const promptResult = window.prompt(t("cancelReasonPrompt"));
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
    } catch (e: any) {
      alert(e?.message ?? t("cancelFailed"));
    } finally {
      setActionLoading(null);
    }
  }

  const pending = bookings.filter((b) => b.status === "pending");
  const confirmed = bookings.filter((b) => b.status === "confirmed");
  const completed = bookings.filter((b) => b.status === "completed");

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
          {t("tryAgain")}
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
          className="text-dash-navy hover:opacity-70"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-h3 font-bold text-dash-navy">{t("heading")}</h1>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-content-secondary uppercase tracking-wide">
          {t("pendingRequests", { count: pending.length })}
        </h2>
        {pending.length === 0 ? (
          <div className="rounded-2xl bg-surface-bg p-6 text-center">
            <p className="text-sm text-content-muted">{t("noPending")}</p>
          </div>
        ) : (
          pending.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              variant="driver"
              booking={booking}
              onConfirm={() => handleConfirm(booking.booking_id)}
              onReject={() => handleReject(booking.booking_id)}
              onViewMap={ride ? () => setMapBooking(booking) : undefined}
              actionLoading={actionLoading === booking.booking_id}
              viewProfileHref={`/users/${booking.passenger_id}`}
            />
          ))
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-content-secondary uppercase tracking-wide">
          {t("confirmedPassengers", { count: confirmed.length })}
        </h2>
        {confirmed.length === 0 ? (
          <div className="rounded-2xl bg-surface-bg p-6 text-center">
            <p className="text-sm text-content-muted">{t("noConfirmed")}</p>
          </div>
        ) : (
          confirmed.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              variant="driver"
              booking={booking}
              cancelAvailable={true}
              onCancel={() => handleCancel(booking.booking_id)}
              onViewMap={ride ? () => setMapBooking(booking) : undefined}
              actionLoading={actionLoading === booking.booking_id}
              viewProfileHref={`/users/${booking.passenger_id}`}
            />
          ))
        )}
      </section>

      {completed.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-content-secondary uppercase tracking-wide">
            {t("completed", { count: completed.length })}
          </h2>
          {completed.map((booking) => {
            const passengerName = booking.passenger.display_name ?? tNav("defaultPassengerName");
            const initials = passengerName
              .split(" ")
              .map((w) => w[0])
              .slice(0, 2)
              .join("")
              .toUpperCase();
            return (
              <div
                key={booking.booking_id}
                className="rounded-2xl bg-surface-bg p-4 space-y-4"
              >
                <div className="flex items-center gap-3">
                  {booking.passenger.avatar_url ? (
                    <img
                      src={booking.passenger.avatar_url}
                      alt={passengerName}
                      className="h-12 w-12 rounded-full object-cover shrink-0"
                    />
                  ) : (
                    <div className="h-12 w-12 rounded-full bg-surface-card flex items-center justify-center shrink-0 text-sm font-semibold text-content-secondary">
                      {initials}
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="font-semibold text-dash-navy truncate">{passengerName}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="rounded-full bg-surface-card px-2.5 py-1 text-xs font-medium text-content-secondary">
                        {formatCurrency(Number(booking.total_price), locale)}
                        {booking.seats > 1 ? ` · ${booking.seats} ${t("seats")}` : ""}
                      </span>
                      <RatingBadge
                        ratingAvg={booking.passenger.rating_avg ?? null}
                        ratingCount={booking.passenger.rating_count ?? 0}
                      />
                    </div>
                  </div>
                </div>
                <Link
                  href={`/ratings/${booking.booking_id}`}
                  className="block w-full text-center rounded-xl bg-dash-primary hover:opacity-90 text-white py-3 text-sm font-semibold transition-opacity"
                >
                  {t("rateAndReport")}
                </Link>
                <Link
                  href={`/users/${booking.passenger_id}`}
                  className="flex items-center justify-between text-xs font-medium px-3 py-2 rounded-lg bg-surface-card border border-transparent hover:border-border-default text-dash-primary transition-colors"
                >
                  <span>{t("viewProfile")}</span>
                  <span className="text-content-muted">→</span>
                </Link>
              </div>
            );
          })}
        </section>
      )}

      <BottomSheet isOpen={!!mapBooking} onClose={() => setMapBooking(null)}>
        {mapBooking && ride && (
          <div className="space-y-3 pt-1">
            <h2 className="text-base font-semibold text-content-primary">
              {t("pickupDropoffMapTitle", { name: mapBooking.passenger.display_name ?? tNav("defaultPassengerName") })}
            </h2>
            <RideDetailMap
              routeGeometry={ride.route_geometry}
              boardingPoint={mapBooking.boarding_point}
              alightingPoint={mapBooking.alighting_point}
              origin={ride.origin.coordinates}
              destination={ride.destination.coordinates}
            />
          </div>
        )}
      </BottomSheet>

      <VerificationRequiredModal
        isOpen={verifyModalOpen}
        onClose={() => setVerifyModalOpen(false)}
        role="driver"
      />
    </div>
  );
}
