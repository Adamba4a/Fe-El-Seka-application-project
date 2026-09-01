"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useSession } from "@/lib/auth/hooks";
import { getMe } from "@/lib/api/profiles";
import { getNearbyRides, type NearbyRide } from "@/lib/api/search";
import { listBookings, type PassengerBooking } from "@/lib/api/bookings";
import { getLoyaltyBalance } from "@/lib/api/loyalty";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Profile, Locale } from "@fe-el-seka/shared";
import { AvailableRideCard } from "@/components/passenger/AvailableRideCard";
import { JoinedRideCard } from "@/components/passenger/JoinedRideCard";

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function formatDepartureLabel(iso: string, locale: Locale, dayToday: string, dayTomorrow: string): string {
  const date = new Date(iso);
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);

  const intlLocale = locale === "ar" ? "ar-EG" : "en-EG";

  let dayLabel: string;
  if (isSameDay(date, now)) dayLabel = dayToday;
  else if (isSameDay(date, tomorrow)) dayLabel = dayTomorrow;
  else
    dayLabel = new Intl.DateTimeFormat(intlLocale, {
      month: "short",
      day: "numeric",
      numberingSystem: "latn",
    }).format(date).toUpperCase();

  const time = new Intl.DateTimeFormat(intlLocale, {
    hour: "numeric",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(date).toUpperCase();
  return `${dayLabel} • ${time}`;
}

function formatDistanceLabel(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m away`;
  return `${(meters / 1000).toFixed(1)} km away`;
}

type GeoState = "idle" | "loading" | "granted" | "denied";

export function PassengerDashboard() {
  const t = useTranslations("passengerDashboard");
  const locale = useLocale() as Locale;
  const session = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [nearby, setNearby] = useState<NearbyRide[]>([]);
  const [nearbyLoading, setNearbyLoading] = useState(true);
  const [geoState, setGeoState] = useState<GeoState>("idle");
  const [joined, setJoined] = useState<PassengerBooking[]>([]);
  const [joinedLoading, setJoinedLoading] = useState(true);
  const [loyaltyBalance, setLoyaltyBalance] = useState<number | null>(null);

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

    getLoyaltyBalance(token)
      .then((res) => setLoyaltyBalance(res.balance))
      .catch(() => {});

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
  const dayToday = t("dayToday");
  const dayTomorrow = t("dayTomorrow");

  return (
    <div className="pb-6">
      <h1 className="text-2xl font-bold text-dash-navy mt-2">{t("greeting", { name: firstName })}</h1>
      <p className="text-dash-navy mt-1">{t("subtitle")}</p>

      <Link
        href="/search"
        className="mt-4 block w-full text-center rounded-xl bg-dash-primary text-white font-semibold py-3"
      >
        {t("findARide")}
      </Link>

      <div className="mt-6 bg-dash-surface rounded-2xl p-5 border border-dash-border flex items-center justify-between gap-3">
        <div>
          <p className="font-bold text-dash-navy">
            {t("loyaltyPointsTitle")}
            {loyaltyBalance != null && (
              <span className="ms-2 text-sm font-semibold text-dash-primary">
                {t("loyaltyPointsBalance", { points: loyaltyBalance })}
              </span>
            )}
          </p>
          <p className="text-sm text-dash-text-muted mt-1">{t("loyaltyPointsBody")}</p>
        </div>
        <Link href="/loyalty" className="shrink-0 text-xs font-semibold text-dash-primary whitespace-nowrap">
          {t("viewLoyaltyPoints")}
        </Link>
      </div>

      <h2 className="text-xl font-bold text-dash-navy mt-8 mb-3">{t("ridesNearYou")}</h2>

      {nearbyLoading ? (
        <div className="space-y-3">
          <div className="h-40 bg-dash-surface rounded-2xl animate-pulse" />
          <div className="h-40 bg-dash-surface rounded-2xl animate-pulse" />
        </div>
      ) : geoState === "denied" ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">{t("enableLocationTitle")}</p>
          <p className="text-sm text-dash-text-muted mt-1">
            {t("enableLocationBody")}
          </p>
          <Link href="/search" className="text-sm text-dash-primary font-semibold mt-2 inline-block">
            {t("goToSearch")}
          </Link>
        </div>
      ) : nearby.length === 0 ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">{t("noNearbyTitle")}</p>
          <p className="text-sm text-dash-text-muted mt-1">{t("noNearbyBody")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {nearby.map((ride) => (
            <AvailableRideCard
              key={ride.ride_id}
              rideId={ride.ride_id}
              departureLabel={formatDepartureLabel(ride.departure_datetime, locale, dayToday, dayTomorrow)}
              originAddress={ride.origin_address}
              destinationAddress={ride.destination_address}
              price={formatCurrency(Number(ride.per_seat_price), locale)}
              distanceLabel={formatDistanceLabel(ride.distance_meters)}
              driverName={ride.driver.display_name}
              driverAvatarUrl={ride.driver.avatar_url}
              isVerified={ride.driver.is_verified}
              driverRatingAvg={ride.driver.rating_avg}
              driverRatingCount={ride.driver.rating_count}
            />
          ))}
        </div>
      )}

      <h2 className="text-xl font-bold text-dash-navy mt-8 mb-3">{t("myJoinedRides")}</h2>

      {joinedLoading ? (
        <div className="h-32 bg-dash-surface rounded-2xl animate-pulse" />
      ) : joined.length === 0 ? (
        <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
          <p className="text-dash-navy font-medium">{t("noActiveBookingsTitle")}</p>
          <p className="text-sm text-dash-text-muted mt-1">{t("noActiveBookingsBody")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {joined.map((booking) => (
            <JoinedRideCard
              key={booking.booking_id}
              href={`/bookings/${booking.booking_id}`}
              departureLabel={
                booking.departure_datetime
                  ? formatDepartureLabel(booking.departure_datetime, locale, dayToday, dayTomorrow)
                  : "—"
              }
              originAddress={booking.origin_address}
              destinationAddress={booking.destination_address}
              status={booking.status}
              driverName={booking.driver_display_name}
              price={formatCurrency(Number(booking.total_price), locale)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
