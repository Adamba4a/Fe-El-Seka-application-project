"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "@/lib/auth/hooks";
import { getMe } from "@/lib/api/profiles";
import { getNearbyRides, type NearbyRide } from "@/lib/api/search";
import { listBookings, type PassengerBooking } from "@/lib/api/bookings";
import type { Profile } from "@fe-el-seka/shared";
import { AvailableRideCard } from "@/components/passenger/AvailableRideCard";
import { JoinedRideCard } from "@/components/passenger/JoinedRideCard";

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function formatDepartureLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);

  let dayLabel: string;
  if (isSameDay(date, now)) dayLabel = "TODAY";
  else if (isSameDay(date, tomorrow)) dayLabel = "TOMORROW";
  else dayLabel = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }).toUpperCase();

  const time = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toUpperCase();
  return `${dayLabel} • ${time}`;
}

function formatDistanceLabel(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m away`;
  return `${(meters / 1000).toFixed(1)} km away`;
}

type GeoState = "idle" | "loading" | "granted" | "denied";

export function PassengerDashboard() {
  const session = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [nearby, setNearby] = useState<NearbyRide[]>([]);
  const [nearbyLoading, setNearbyLoading] = useState(true);
  const [geoState, setGeoState] = useState<GeoState>("idle");
  const [joined, setJoined] = useState<PassengerBooking[]>([]);
  const [joinedLoading, setJoinedLoading] = useState(true);

  useEffect(() => {
    if (!session?.access_token) return;
    const token = session.access_token;

    getMe(token).then(setProfile).catch(() => {});

    listBookings(token, { page_size: 50 })
      .then((res) => {
        const active = res.bookings
          .filter((b) => b.status === "pending" || b.status === "confirmed")
          .sort((a, b) => new Date(a.departure_datetime ?? 0).getTime() - new Date(b.departure_datetime ?? 0).getTime())
          .slice(0, 2);
        setJoined(active);
      })
      .catch(() => {})
      .finally(() => setJoinedLoading(false));

    if (!navigator.geolocation) {
      setGeoState("denied");
      setNearbyLoading(false);
      return;
    }

    setGeoState("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoState("granted");
        getNearbyRides(token, pos.coords.latitude, pos.coords.longitude, 2)
          .then(setNearby)
          .catch(() => {})
          .finally(() => setNearbyLoading(false));
      },
      () => {
        setGeoState("denied");
        setNearbyLoading(false);
      },
      { timeout: 8000 }
    );
  }, [session]);

  const name = profile?.display_name ?? "Passenger";
  const firstName = name.split(" ")[0];

  return (
    <div className="pb-6">
      <h1 className="text-2xl font-bold text-dash-navy mt-2">Ahlan, {firstName}!</h1>
      <p className="text-dash-navy mt-1">Where are you headed today?</p>

      <Link
        href="/search"
        className="mt-4 block w-full text-center rounded-xl bg-dash-primary text-white font-semibold py-3"
      >
        Find a Ride
      </Link>

      <h2 className="text-xl font-bold text-dash-navy mt-8 mb-3">Rides Near You</h2>

      {nearbyLoading ? (
        <div className="space-y-3">
          <div className="h-40 bg-dash-surface rounded-2xl animate-pulse" />
          <div className="h-40 bg-dash-surface rounded-2xl animate-pulse" />
        </div>
      ) : geoState === "denied" ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">Enable location to see nearby rides</p>
          <p className="text-sm text-dash-text-muted mt-1">
            Or search directly with your pickup and drop-off.
          </p>
          <Link href="/search" className="text-sm text-dash-primary font-semibold mt-2 inline-block">
            Go to Search →
          </Link>
        </div>
      ) : nearby.length === 0 ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">No rides near you right now</p>
          <p className="text-sm text-dash-text-muted mt-1">Try searching for your full route instead.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {nearby.map((ride) => (
            <AvailableRideCard
              key={ride.ride_id}
              rideId={ride.ride_id}
              departureLabel={formatDepartureLabel(ride.departure_datetime)}
              originAddress={ride.origin_address}
              destinationAddress={ride.destination_address}
              price={ride.per_seat_price}
              distanceLabel={formatDistanceLabel(ride.distance_meters)}
              driverName={ride.driver.display_name}
              driverAvatarUrl={ride.driver.avatar_url}
              isVerified={ride.driver.is_verified}
            />
          ))}
        </div>
      )}

      <h2 className="text-xl font-bold text-dash-navy mt-8 mb-3">My Joined Rides</h2>

      {joinedLoading ? (
        <div className="h-32 bg-dash-surface rounded-2xl animate-pulse" />
      ) : joined.length === 0 ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">No active bookings</p>
          <p className="text-sm text-dash-text-muted mt-1">Rides you join will show up here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {joined.map((booking) => (
            <JoinedRideCard
              key={booking.booking_id}
              href={`/bookings/${booking.booking_id}`}
              departureLabel={booking.departure_datetime ? formatDepartureLabel(booking.departure_datetime) : "—"}
              originAddress={booking.origin_address}
              destinationAddress={booking.destination_address}
              status={booking.status}
              driverName={booking.driver_display_name}
              price={booking.total_price}
            />
          ))}
        </div>
      )}
    </div>
  );
}
