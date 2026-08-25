"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getDetail, featureRide, unfeatureRide, type RideDetailResponse, type RideStatus } from "@/lib/api/admin-rides";

const sb = createAdminBrowserClient();

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export default function RideDetailPage({ params }: { params: { ride_id: string } }) {
  const [detail, setDetail] = useState<RideDetailResponse | null>(null);
  const [error, setError] = useState("");
  const [toggling, setToggling] = useState(false);
  const [toggleError, setToggleError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await sb.auth.getSession();
        const token = data.session?.access_token ?? "";
        const res = await getDetail(token, params.ride_id);
        if (!cancelled) setDetail(res);
      } catch {
        if (!cancelled) setError("Ride not found");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.ride_id]);

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!detail) return <main className="p-8 text-gray-400">Loading…</main>;

  const { ride, bookings } = detail;

  async function toggleFeatured() {
    setToggling(true);
    setToggleError("");
    try {
      const { data: session } = await sb.auth.getSession();
      const token = session.session?.access_token ?? "";
      const result = ride.is_featured
        ? await unfeatureRide(token, ride.ride_id)
        : await featureRide(token, ride.ride_id);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              ride: { ...prev.ride, is_featured: result.is_featured, featured_at: result.featured_at },
            }
          : prev
      );
    } catch (e) {
      const message =
        e && typeof e === "object" && "message" in e ? String((e as { message: unknown }).message) : "Failed to update Featured status.";
      setToggleError(message);
    } finally {
      setToggling(false);
    }
  }

  return (
    <main className="p-8 space-y-8 max-w-3xl">
      <div className="flex items-center gap-4">
        <Link href="/rides" className="text-sm text-blue-600 hover:underline">← Rides</Link>
        <h1 className="text-xl font-semibold">Ride Detail</h1>
      </div>

      <section className="space-y-3">
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-gray-500">Ride ID</dt>
          <dd className="flex items-center gap-2">
            <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded select-all">{ride.ride_id}</code>
          </dd>
          <dt className="text-gray-500">Route</dt>
          <dd>{ride.origin_address} → {ride.destination_address}</dd>
          <dt className="text-gray-500">Departure</dt>
          <dd>{new Date(ride.departure_datetime).toLocaleString()}</dd>
          <dt className="text-gray-500">Status</dt>
          <dd>
            <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_STYLES[ride.status]}`}>
              {ride.status.replace(/_/g, " ")}
            </span>
          </dd>
          <dt className="text-gray-500">Seats</dt>
          <dd>{ride.booked_seats} booked / {ride.total_seats} total ({ride.available_seats} available)</dd>
          <dt className="text-gray-500">Price per seat</dt>
          <dd>{ride.price_per_seat} EGP</dd>
          {ride.notes && (
            <>
              <dt className="text-gray-500">Notes</dt>
              <dd>{ride.notes}</dd>
            </>
          )}
          {ride.status === "cancelled" && (
            <>
              <dt className="text-gray-500">Cancellation reason</dt>
              <dd>{ride.cancellation_reason} ({ride.cancellation_source})</dd>
            </>
          )}
          <dt className="text-gray-500">Created</dt>
          <dd>{new Date(ride.created_at).toLocaleString()}</dd>
          <dt className="text-gray-500">Featured</dt>
          <dd className="flex items-center gap-2">
            <button
              type="button"
              disabled={toggling}
              onClick={toggleFeatured}
              className={`px-2 py-0.5 rounded text-xs font-medium disabled:opacity-50 ${
                ride.is_featured ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"
              }`}
            >
              {toggling ? "…" : ride.is_featured ? "★ Featured — click to unfeature" : "Feature this ride"}
            </button>
            {ride.is_featured && ride.featured_by_display_name && (
              <span className="text-xs text-gray-500">by {ride.featured_by_display_name}</span>
            )}
          </dd>
          {toggleError && (
            <>
              <dt />
              <dd className="text-xs text-red-600">{toggleError}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Driver</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-gray-500">Name</dt>
          <dd>
            <Link href={`/users/${ride.driver.driver_id}`} className="text-blue-600 hover:underline">
              {ride.driver.display_name || "—"}
            </Link>
          </dd>
          <dt className="text-gray-500">Email</dt><dd>{ride.driver.email}</dd>
          <dt className="text-gray-500">Rating</dt>
          <dd>
            {ride.driver.rating_avg !== null
              ? `${ride.driver.rating_avg.toFixed(2)} (${ride.driver.rating_count})`
              : "No ratings yet"}
          </dd>
        </dl>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Vehicle</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-gray-500">Plate</dt><dd>{ride.vehicle.plate_number}</dd>
          <dt className="text-gray-500">Make / Model</dt><dd>{ride.vehicle.make} {ride.vehicle.model}</dd>
          <dt className="text-gray-500">Color</dt><dd>{ride.vehicle.color}</dd>
        </dl>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Bookings ({bookings.length})</h2>
        {bookings.length === 0 ? (
          <p className="text-sm text-gray-400">No bookings yet.</p>
        ) : (
          <ul className="text-sm divide-y border rounded">
            {bookings.map((b) => (
              <li key={b.booking_id} className="flex items-center justify-between px-3 py-2">
                <Link href={`/users/${b.passenger_id}`} className="text-blue-600 hover:underline">
                  {b.passenger_display_name || "—"}
                </Link>
                <span className="capitalize">{b.status.replace(/_/g, " ")}</span>
                <span>{b.seats} seat{b.seats !== 1 ? "s" : ""}</span>
                <span>{b.total_price} EGP</span>
                <span className="text-gray-500">{new Date(b.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
