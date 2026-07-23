"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { MatchScoreBadge } from "@/components/search/MatchScoreBadge";
import { env } from "@/lib/env";

const RideDetailMap = dynamic(
  () => import("@/components/bookings/RideDetailMap").then((m) => ({ default: m.RideDetailMap })),
  { ssr: false, loading: () => <div className="w-full h-56 bg-surface-bg rounded-xl animate-pulse" /> }
);

interface DriverInfo {
  display_name: string | null;
  avatar_url: string | null;
  is_verified: boolean;
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

interface RideDetail {
  id: string;
  status: string;
  driver: DriverInfo;
  departure_datetime: string;
  available_seats: number;
  per_seat_price: string;
  route_geometry: object | null;
  route_distance_km: number;
  route_duration_minutes: number;
}

interface DetailResponse {
  ride: RideDetail;
  passenger_context: PassengerContext;
  match_score_pct: number | null;
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
}

type PremiumOption = "standard" | "premium_pickup" | "premium_dropoff" | "premium_both";

function formatDeparture(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PassengerRideDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

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
  const [showSheet, setShowSheet] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);

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
          if (!res.ok) { setError("Failed to load ride details."); return; }

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
        if (!res.ok) { setError("Failed to load ride details."); return; }

        const json: DetailResponse = await res.json();
        setDetail(json);
      } catch {
        setError("Network error — please check your connection.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, hasParams]); // eslint-disable-line react-hooks/exhaustive-deps

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
        <p className="text-lg font-semibold text-content-primary">Ride no longer available</p>
        <p className="text-sm text-content-muted">This ride has been cancelled or completed.</p>
        <button
          onClick={() => router.push("/search")}
          className="text-sm text-brand-primary font-medium"
        >
          Search for another ride
        </button>
      </div>
    );
  }

  if (!hasParams) {
    if (error || !preview) {
      return (
        <div className="py-16 text-center">
          <p className="text-sm text-content-destructive">{error ?? "Something went wrong."}</p>
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
          ← Back
        </button>

        <div className="flex items-center gap-3 p-4 bg-surface-card border border-border-default rounded-xl">
          {preview.driver.avatar_url ? (
            <img
              src={preview.driver.avatar_url}
              alt={preview.driver.display_name ?? "Driver"}
              className="w-12 h-12 rounded-full object-cover shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-base font-semibold text-content-secondary">
              {(preview.driver.display_name ?? "?")[0].toUpperCase()}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-content-primary truncate">
              {preview.driver.display_name ?? "Driver"}
            </p>
            {preview.driver.is_verified && (
              <span className="text-xs text-green-600 font-medium">Verified driver</span>
            )}
          </div>
        </div>

        <RideDetailMap
          routeGeometry={preview.route_geometry}
          boardingPoint={null}
          alightingPoint={null}
          origin={preview.origin}
          destination={preview.destination}
        />

        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-content-secondary">
            <span>Route</span>
            <span className="font-medium text-content-primary text-right">
              {preview.origin_address} → {preview.destination_address}
            </span>
          </div>
          <div className="flex justify-between text-content-secondary">
            <span>Departure</span>
            <span className="font-medium text-content-primary">{formatDeparture(preview.departure_datetime)}</span>
          </div>
          {preview.route_duration_minutes != null && (
            <div className="flex justify-between text-content-secondary">
              <span>Ride time</span>
              <span className="font-medium text-content-primary">{preview.route_duration_minutes} min</span>
            </div>
          )}
          <div className="flex justify-between text-content-secondary">
            <span>Available seats</span>
            <span className={`font-medium ${noSeats ? "text-content-destructive" : "text-content-primary"}`}>
              {noSeats ? "Full" : preview.available_seats}
            </span>
          </div>
          <div className="flex justify-between text-content-secondary">
            <span>Price per seat</span>
            <span className="font-medium text-content-primary">EGP {preview.per_seat_price}</span>
          </div>
        </div>

        <button
          type="button"
          disabled={noSeats}
          onClick={() => {
            const params = new URLSearchParams({ departure_at: preview.departure_datetime });
            router.push(`/rides/${id}/book?${params}`);
          }}
          className="w-full bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
        >
          {noSeats ? "No Seats Available" : "Book Seat"}
        </button>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-content-destructive">{error ?? "Something went wrong."}</p>
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

  const totalPrice = (parseFloat(ride.per_seat_price) + premiumFee).toFixed(2);
  const noSeats = ride.available_seats === 0;

  const handleBook = () => {
    setBookingError(null);
    setShowSheet(true);
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

      const res = await fetch(`${env.apiUrl}/api/v1/bookings`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ride_id: detail.ride.id,
          boarding_point: ctx.boarding_point,
          alighting_point: ctx.alighting_point,
          premium_pickup_requested: premiumOption === "premium_pickup" || premiumOption === "premium_both",
          premium_dropoff_requested: premiumOption === "premium_dropoff" || premiumOption === "premium_both",
          premium_pickup_fee: pickupFee,
          premium_dropoff_fee: dropoffFee,
        }),
      });

      const json = await res.json();
      if (res.status === 201) {
        router.push(`/bookings/${json.booking_id}`);
        return;
      }
      if (res.status === 409) {
        setBookingError(
          json.error === "duplicate_booking"
            ? "You already have a booking for this ride."
            : "No seats available — this ride just filled up."
        );
      } else {
        setBookingError(json.message ?? "Booking failed. Please try again.");
      }
    } catch {
      setBookingError("Network error — please try again.");
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
        ← Back to results
      </button>

      {/* Driver card */}
      <div className="flex items-center gap-3 p-4 bg-surface-card border border-border-default rounded-xl">
        {ride.driver.avatar_url ? (
          <img
            src={ride.driver.avatar_url}
            alt={ride.driver.display_name ?? "Driver"}
            className="w-12 h-12 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-base font-semibold text-content-secondary">
            {(ride.driver.display_name ?? "?")[0].toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-content-primary truncate">
            {ride.driver.display_name ?? "Driver"}
          </p>
          {ride.driver.is_verified && (
            <span className="text-xs text-green-600 font-medium">Verified driver</span>
          )}
        </div>
      </div>

      {detail.match_score_pct !== null && (
        <MatchScoreBadge score_pct={detail.match_score_pct} />
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
          <span>Departure</span>
          <span className="font-medium text-content-primary">{formatDeparture(ride.departure_datetime)}</span>
        </div>
        {ctx.estimated_travel_minutes && (
          <div className="flex justify-between text-content-secondary">
            <span>Estimated ride time</span>
            <span className="font-medium text-content-primary">{ctx.estimated_travel_minutes} min</span>
          </div>
        )}
        <div className="flex justify-between text-content-secondary">
          <span>Walk to pickup</span>
          <span className="font-medium text-content-primary">{ctx.pickup_walk_meters}m</span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>Walk from dropoff</span>
          <span className="font-medium text-content-primary">{ctx.dropoff_walk_meters}m</span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>Available seats</span>
          <span className={`font-medium ${noSeats ? "text-content-destructive" : "text-content-primary"}`}>
            {noSeats ? "Full" : ride.available_seats}
          </span>
        </div>
        <div className="flex justify-between text-content-secondary">
          <span>Base price</span>
          <span className="font-medium text-content-primary">EGP {ride.per_seat_price}</span>
        </div>
      </div>

      {/* Premium options */}
      {hasPremium && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-content-primary">Pickup / Dropoff Option</p>

          <button
            type="button"
            onClick={() => setPremiumOption("standard")}
            className={`w-full flex items-center justify-between p-3 rounded-xl border text-sm transition-colors ${
              premiumOption === "standard"
                ? "border-brand-primary bg-brand-primary/5"
                : "border-border-default bg-surface-card"
            }`}
          >
            <span className="font-medium text-content-primary">Standard</span>
            <span className="text-content-muted">EGP {ride.per_seat_price}</span>
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
              <span className="text-amber-600">+EGP {(ctx.premium_pickup_fee ?? 0).toFixed(2)}</span>
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
              <span className="text-amber-600">+EGP {(ctx.premium_dropoff_fee ?? 0).toFixed(2)}</span>
            </button>
          )}
        </div>
      )}

      {/* Price summary + Book button */}
      <div className="space-y-3 pt-2 border-t border-border-default">
        <div className="flex justify-between text-sm font-semibold text-content-primary">
          <span>Total</span>
          <span>EGP {totalPrice}</span>
        </div>

        <button
          type="button"
          disabled={noSeats}
          onClick={handleBook}
          className="w-full bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
        >
          {noSeats ? "No Seats Available" : "Book Seat"}
        </button>
      </div>

      {/* Booking confirmation bottom sheet */}
      <BottomSheet isOpen={showSheet} onClose={() => { setShowSheet(false); setBookingError(null); }}>
        <div className="space-y-4 pt-1">
          <h2 className="text-base font-semibold text-content-primary">Confirm Booking</h2>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-content-secondary">
              <span>Driver</span>
              <span className="font-medium text-content-primary">{ride.driver.display_name ?? "—"}</span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>Departure</span>
              <span className="font-medium text-content-primary">{formatDeparture(ride.departure_datetime)}</span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>Pickup</span>
              <span className="font-medium text-content-primary">
                {ctx.pickup_walk_meters}m walk to boarding point
              </span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>Dropoff</span>
              <span className="font-medium text-content-primary">
                {ctx.dropoff_walk_meters}m walk from alighting point
              </span>
            </div>
          </div>

          <div className="border-t border-border-default pt-3 space-y-1 text-sm">
            <div className="flex justify-between text-content-secondary">
              <span>Base fare</span>
              <span>EGP {ride.per_seat_price}</span>
            </div>
            {(premiumOption === "premium_pickup" || premiumOption === "premium_both") && ctx.premium_pickup_fee && (
              <div className="flex justify-between text-amber-700">
                <span>Premium pickup</span>
                <span>+EGP {ctx.premium_pickup_fee.toFixed(2)}</span>
              </div>
            )}
            {(premiumOption === "premium_dropoff" || premiumOption === "premium_both") && ctx.premium_dropoff_fee && (
              <div className="flex justify-between text-amber-700">
                <span>Premium dropoff</span>
                <span>+EGP {ctx.premium_dropoff_fee.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between font-semibold text-content-primary pt-1 border-t border-border-default">
              <span>Total</span>
              <span>EGP {totalPrice}</span>
            </div>
          </div>

          {bookingError && (
            <p className="text-sm text-content-destructive">{bookingError}</p>
          )}

          <button
            type="button"
            onClick={confirmBooking}
            disabled={bookingLoading}
            className="w-full flex items-center justify-center gap-2 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
          >
            {bookingLoading && <Spinner />}
            {bookingLoading ? "Booking…" : "Confirm Booking"}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
