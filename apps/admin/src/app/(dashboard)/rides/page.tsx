"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { list, featureRide, unfeatureRide, type RideListItem, type RideStatus } from "@/lib/api/admin-rides";

const sb = createAdminBrowserClient();

const STATUSES: { value: RideStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "scheduled", label: "Scheduled" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const PAGE_SIZE = 20;

const STATUS_STYLES: Record<RideStatus, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export default function RidesPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<RideStatus | "">("");
  const [date, setDate] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<RideListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<{ rideId: string; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const timeout = setTimeout(async () => {
      try {
        const { data: session } = await sb.auth.getSession();
        const token = session.session?.access_token ?? "";
        const res = await list(token, {
          q: q.trim() || undefined,
          status: status || undefined,
          date: date || undefined,
          page,
        });
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
        }
      } catch {
        if (!cancelled) setError("Failed to load rides.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [q, status, date, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function toggleFeatured(ride: RideListItem) {
    setTogglingId(ride.ride_id);
    setToggleError(null);
    try {
      const { data: session } = await sb.auth.getSession();
      const token = session.session?.access_token ?? "";
      const result = ride.is_featured
        ? await unfeatureRide(token, ride.ride_id)
        : await featureRide(token, ride.ride_id);
      setItems((prev) =>
        prev.map((r) =>
          r.ride_id === ride.ride_id
            ? { ...r, is_featured: result.is_featured, featured_at: result.featured_at }
            : r
        )
      );
    } catch (e) {
      const message =
        e && typeof e === "object" && "message" in e ? String((e as { message: unknown }).message) : "Failed to update Featured status.";
      setToggleError({ rideId: ride.ride_id, message });
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <main className="p-8 space-y-6 max-w-5xl">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-xl font-semibold">Rides ({total})</h1>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Search driver or address…"
          className="border rounded px-3 py-1.5 text-sm w-64"
        />
        <select
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value as RideStatus | "");
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <input
          type="date"
          value={date}
          onChange={(e) => {
            setPage(1);
            setDate(e.target.value);
          }}
          className="border rounded px-3 py-1.5 text-sm"
        />
        {date && (
          <button
            type="button"
            onClick={() => {
              setPage(1);
              setDate("");
            }}
            className="text-sm text-blue-600 hover:underline"
          >
            Clear date
          </button>
        )}
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-2 pr-4 font-medium">Route</th>
            <th className="py-2 pr-4 font-medium">Driver</th>
            <th className="py-2 pr-4 font-medium">Departure</th>
            <th className="py-2 pr-4 font-medium">Seats</th>
            <th className="py-2 pr-4 font-medium">Price</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 pr-4 font-medium">Featured</th>
            <th className="py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.ride_id} className="border-b hover:bg-gray-50">
              <td className="py-2 pr-4">
                {r.origin_address} → {r.destination_address}
              </td>
              <td className="py-2 pr-4">{r.driver_display_name || "—"}</td>
              <td className="py-2 pr-4 text-gray-600">
                {new Date(r.departure_datetime).toLocaleString()}
              </td>
              <td className="py-2 pr-4">{r.booked_seats}/{r.total_seats}</td>
              <td className="py-2 pr-4">{r.price_per_seat} EGP</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_STYLES[r.status]}`}>
                  {r.status.replace(/_/g, " ")}
                </span>
              </td>
              <td className="py-2 pr-4">
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    disabled={togglingId === r.ride_id}
                    onClick={() => toggleFeatured(r)}
                    className={`px-2 py-0.5 rounded text-xs font-medium disabled:opacity-50 ${
                      r.is_featured ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {togglingId === r.ride_id ? "…" : r.is_featured ? "★ Featured" : "Feature"}
                  </button>
                  {toggleError?.rideId === r.ride_id && (
                    <span className="text-xs text-red-600">{toggleError.message}</span>
                  )}
                </div>
              </td>
              <td className="py-2">
                <Link href={`/rides/${r.ride_id}`} className="text-blue-600 hover:underline">
                  Detail
                </Link>
              </td>
            </tr>
          ))}
          {!loading && items.length === 0 && (
            <tr>
              <td colSpan={8} className="py-8 text-center text-gray-400">No rides found</td>
            </tr>
          )}
        </tbody>
      </table>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="flex items-center gap-4 text-sm">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          className="text-blue-600 hover:underline disabled:text-gray-300 disabled:no-underline"
        >
          Previous
        </button>
        <span className="text-gray-500">Page {page} of {totalPages}</span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          className="text-blue-600 hover:underline disabled:text-gray-300 disabled:no-underline"
        >
          Next
        </button>
      </div>
    </main>
  );
}
