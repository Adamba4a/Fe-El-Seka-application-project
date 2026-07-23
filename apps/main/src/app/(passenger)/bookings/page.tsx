"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { BookingCard } from "@/components/bookings/BookingCard";
import { createClient } from "@/lib/supabase/client";
import { useSession } from "@/lib/auth/hooks";
import { useBookingStatus } from "@/lib/hooks/useBookingStatus";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";
type Tab = "all" | "active" | "past";

interface PassengerBooking {
  booking_id: string;
  ride_id: string;
  status: BookingStatus;
  driver_display_name?: string;
  departure_datetime?: string;
  per_seat_price: string;
  total_price: string;
  premium_pickup_requested: boolean;
  premium_dropoff_requested: boolean;
  created_at: string;
  confirmed_at?: string | null;
  cancelled_at?: string | null;
}

async function apiFetch(path: string) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
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

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "past", label: "Past" },
];

function filterByTab(bookings: PassengerBooking[], tab: Tab): PassengerBooking[] {
  if (tab === "active") return bookings.filter((b) => b.status === "pending" || b.status === "confirmed");
  if (tab === "past") return bookings.filter((b) => b.status === "completed" || b.status === "cancelled");
  return bookings;
}

export default function PassengerBookingsPage() {
  const router = useRouter();
  const session = useSession();
  const userId = session?.user.id;
  const [bookings, setBookings] = useState<PassengerBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("all");

  const { lastEvent } = useBookingStatus({ passengerId: userId });

  // Apply real-time UPDATE events to local state without a full refetch
  useEffect(() => {
    if (!lastEvent || lastEvent.eventType !== "UPDATE") return;
    const updated = lastEvent.new as { id?: string; status?: BookingStatus };
    if (!updated?.id || !updated?.status) return;
    setBookings((prev) =>
      prev.map((b) =>
        b.booking_id === updated.id ? { ...b, status: updated.status! } : b
      )
    );
  }, [lastEvent]);

  const fetchBookings = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch("/api/v1/bookings");
      setBookings(data.bookings ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load bookings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const visible = filterByTab(bookings, activeTab);

  return (
    <div className="max-w-md mx-auto p-4 space-y-4">
      <h1 className="text-xl font-semibold">My Bookings</h1>

      {/* Tab bar */}
      <div className="flex border-b border-border-default">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-brand-primary text-brand-primary"
                : "text-content-muted hover:text-content-primary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      )}

      {!loading && error && (
        <div className="text-center py-12 text-destructive space-y-2">
          <p>{error}</p>
          <button className="text-sm underline" onClick={fetchBookings}>
            Try again
          </button>
        </div>
      )}

      {!loading && !error && visible.length === 0 && (
        <div className="text-center py-16 text-content-muted space-y-1">
          <p className="font-medium">No bookings here</p>
          <p className="text-sm">
            {activeTab === "active"
              ? "You have no pending or confirmed bookings."
              : activeTab === "past"
              ? "No completed or cancelled bookings yet."
              : "You haven't made any bookings yet."}
          </p>
        </div>
      )}

      {!loading && !error && visible.length > 0 && (
        <div className="space-y-3">
          {visible.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              variant="passenger"
              booking={booking}
              onClick={() => router.push(`/bookings/${booking.booking_id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
