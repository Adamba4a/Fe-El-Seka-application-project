"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getRecurringSeries, type RecurringSeriesResponse, type RideStatus } from "@/lib/api/admin-rides";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";

const sb = createAdminBrowserClient();

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export default function RecurringSeriesPage({ params }: { params: { definition_id: string } }) {
  const [series, setSeries] = useState<RecurringSeriesResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await sb.auth.getSession();
        const result = await getRecurringSeries(data.session?.access_token ?? "", params.definition_id);
        if (!cancelled) setSeries(result);
      } catch {
        if (!cancelled) setError("Recurring series not found");
      }
    })();
    return () => { cancelled = true; };
  }, [params.definition_id]);

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!series) return <main className="p-8 text-gray-400">Loading…</main>;

  return (
    <main className="max-w-5xl space-y-6 p-8">
      <div className="flex items-center gap-4">
        <Link href="/rides" className="text-sm text-blue-600 hover:underline">← Rides</Link>
        <div>
          <h1 className="text-xl font-semibold">Recurring ride series</h1>
          <p className="text-sm text-gray-500">Driver: <Link className="text-blue-600 hover:underline" href={`/users/${series.driver.driver_id}`}>{series.driver.display_name || "—"}</Link> · {series.occurrences.length} rides, including history</p>
        </div>
      </div>

      <div className="space-y-4">
        {series.occurrences.map((ride) => (
          <section key={ride.ride_id} className="rounded border bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium">{ride.trip_leg === "return" ? "Coming" : "Going"} · {ride.origin_address} → {ride.destination_address}</p>
                <p className="mt-1 text-sm text-gray-500">{new Date(ride.departure_datetime).toLocaleString()} · {ride.booked_seats}/{ride.total_seats} seats · {ride.price_per_seat} EGP</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[ride.status]}`}>{ride.status.replace(/_/g, " ")}</span>
                <Link href={`/rides/${ride.ride_id}`} className="text-sm text-blue-600 hover:underline">Full details</Link>
              </div>
            </div>
            <div className="mt-4 border-t pt-3">
              <h2 className="text-sm font-semibold">Bookings ({ride.bookings.length})</h2>
              {ride.bookings.length === 0 ? <p className="mt-1 text-sm text-gray-400">No bookings.</p> : (
                <ul className="mt-2 divide-y rounded border text-sm">
                  {ride.bookings.map((booking) => <li key={booking.booking_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <Link href={`/users/${booking.passenger_id}`} className="text-blue-600 hover:underline">{booking.passenger_display_name || "—"}</Link>
                    <span className="capitalize">{booking.status.replace(/_/g, " ")}</span>
                    <span>{booking.seats} seat{booking.seats === 1 ? "" : "s"} · {booking.total_price} EGP</span>
                  </li>)}
                </ul>
              )}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
