"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useSession } from "@/lib/auth/hooks";
import { getMe } from "@/lib/api/profiles";
import { listRides, listRideBookings } from "@/lib/api/rides";
import type { Ride, Profile } from "@fe-el-seka/shared";
import { StatsCard } from "@/components/driver/StatsCard";
import { UpcomingTripCard } from "@/components/driver/UpcomingTripCard";

interface TripPassenger {
  display_name: string | null;
  avatar_url: string | null;
}

interface TripWithPassengers {
  ride: Ride;
  passengers: TripPassenger[];
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function formatDepartureLabel(iso: string, todayLabel: string, tomorrowLabel: string): string {
  const date = new Date(iso);
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);

  let dayLabel: string;
  if (isSameDay(date, now)) dayLabel = todayLabel;
  else if (isSameDay(date, tomorrow)) dayLabel = tomorrowLabel;
  else dayLabel = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }).toUpperCase();

  const time = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toUpperCase();
  return `${dayLabel} • ${time}`;
}

function formatEgpWhole(amount: number): string {
  return Math.round(amount).toLocaleString("en-US");
}

export function DriverDashboard() {
  const t = useTranslations("driverDashboard");
  const tNav = useTranslations("nav");
  const session = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [trips, setTrips] = useState<TripWithPassengers[]>([]);
  const [todayCount, setTodayCount] = useState(0);
  const [earnings, setEarnings] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session?.access_token) return;
    const token = session.access_token;

    (async () => {
      try {
        const [me, scheduled, completed] = await Promise.all([
          getMe(token),
          listRides(token, { status: "scheduled", page_size: 50 }),
          listRides(token, { status: "completed", page_size: 50 }),
        ]);

        setProfile(me);
        setCompletedCount(completed.total);
        const totalEarnings = completed.rides.reduce(
          (sum, r) => sum + parseFloat(r.price_per_seat) * r.booked_seats,
          0
        );
        setEarnings(totalEarnings);

        const now = new Date();
        setTodayCount(scheduled.rides.filter((r) => isSameDay(new Date(r.departure_datetime), now)).length);

        const upcoming = [...scheduled.rides]
          .sort((a, b) => new Date(a.departure_datetime).getTime() - new Date(b.departure_datetime).getTime())
          .slice(0, 2);

        const withPassengers = await Promise.all(
          upcoming.map(async (ride): Promise<TripWithPassengers> => {
            if (ride.booked_seats === 0) return { ride, passengers: [] };
            try {
              const bookings = await listRideBookings(token, ride.id, "confirmed");
              return { ride, passengers: bookings.map((b) => b.passenger) };
            } catch {
              return { ride, passengers: [] };
            }
          })
        );
        setTrips(withPassengers);
      } finally {
        setLoading(false);
      }
    })();
  }, [session]);

  const name = profile?.display_name ?? tNav("defaultDriverName");
  const firstName = name.split(" ")[0];

  return (
    <div className="pb-6">
      <h1 className="text-2xl font-bold text-dash-navy mt-2">{t("greeting", { name: firstName })}</h1>
      <p className="text-dash-navy mt-1">
        {t("scheduledRidesToday", { count: todayCount })}
      </p>

      {loading ? (
        <div className="mt-6 space-y-4">
          <div className="flex gap-3">
            <div className="h-24 w-44 bg-dash-surface rounded-2xl animate-pulse" />
            <div className="h-24 w-44 bg-dash-surface rounded-2xl animate-pulse" />
          </div>
          <div className="h-32 bg-dash-surface rounded-2xl animate-pulse" />
        </div>
      ) : (
        <>
          <div className="flex gap-3 mt-6 overflow-x-auto pb-1 -mx-4 px-4">
            <StatsCard variant="dark" label={t("earningsLabel")} value={`EGP ${formatEgpWhole(earnings)}`} subLabel={t("allTime")} />
            <StatsCard variant="light" label={t("ridesLabel")} value={String(completedCount)} subLabel={t("totalCompleted")} />
          </div>

          <h2 className="text-xl font-bold text-dash-navy mt-8 mb-3">{t("upcomingTrips")}</h2>

          {trips.length === 0 ? (
            <div className="bg-dash-surface rounded-2xl p-6 text-center border border-dash-border">
              <p className="text-dash-navy font-medium">{t("noUpcomingTitle")}</p>
              <p className="text-sm text-dash-text-muted mt-1">{t("noUpcomingBody")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {trips.map(({ ride, passengers }) => (
                <UpcomingTripCard
                  key={ride.id}
                  href={`/rides/${ride.id}/manage`}
                  departureLabel={formatDepartureLabel(ride.departure_datetime, t("dayToday"), t("dayTomorrow"))}
                  originAddress={ride.origin.address}
                  destinationAddress={ride.destination.address}
                  isFull={ride.available_seats === 0}
                  waitingCount={ride.available_seats}
                  price={formatEgpWhole(parseFloat(ride.price_per_seat) * ride.booked_seats)}
                  passengers={passengers}
                />
              ))}
            </div>
          )}
        </>
      )}

      <Link
        href="/rides/new"
        aria-label={t("postRideAriaLabel")}
        className="fixed bottom-24 end-5 w-14 h-14 rounded-full bg-dash-primary text-white flex items-center justify-center text-3xl leading-none shadow-lg z-20"
      >
        +
      </Link>
    </div>
  );
}
