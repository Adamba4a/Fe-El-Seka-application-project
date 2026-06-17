"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getRide } from "@/lib/api/rides";
import { RideStatusBadge } from "@/components/rides/RideStatusBadge";
import { RideHistoryLog } from "@/components/rides/RideHistoryLog";
import { StartCompleteActions } from "@/components/rides/StartCompleteActions";
import type { Ride, RideHistoryEntry } from "@fe-el-seka/shared";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RideDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ride, setRide] = useState<Ride | null>(null);
  const [history, setHistory] = useState<RideHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        const detail = await getRide(session.access_token, id);
        setRide(detail.ride);
        setHistory(detail.history);
      } catch (err: any) {
        setError(err?.detail?.message ?? "Ride not found.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (error || !ride) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-gray-600">{error ?? "Ride not found."}</p>
        <Link href="/driver/rides" className="text-blue-600 text-sm underline">← Back to My Rides</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/driver/rides" className="text-gray-500 hover:text-gray-700">←</Link>
        <h1 className="text-xl font-bold text-gray-900">Ride Detail</h1>
      </div>

      {/* Status + actions bar */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <RideStatusBadge status={ride.status} />
          {ride.status === "scheduled" && (
            <Link
              href={`/driver/rides/${ride.id}/edit`}
              className="text-sm text-blue-600 font-medium hover:underline"
            >
              Edit
            </Link>
          )}
        </div>

        <div className="space-y-2">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide">From</p>
            <p className="text-sm font-medium text-gray-900">{ride.origin.address}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide">To</p>
            <p className="text-sm font-medium text-gray-900">{ride.destination.address}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide">Departure</p>
            <p className="text-sm font-medium text-gray-900">{formatDate(ride.departure_datetime)}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 pt-2 border-t border-gray-100">
          <div className="text-center">
            <p className="text-lg font-bold text-gray-900">{ride.available_seats}</p>
            <p className="text-xs text-gray-400">Available</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-gray-900">{ride.total_seats}</p>
            <p className="text-xs text-gray-400">Total</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-gray-900">EGP {ride.price_per_seat}</p>
            <p className="text-xs text-gray-400">/seat</p>
          </div>
        </div>

        {ride.notes && (
          <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">{ride.notes}</p>
        )}

        {ride.cancellation_reason && (
          <div className="bg-red-50 rounded-lg px-3 py-2">
            <p className="text-xs text-red-500 uppercase tracking-wide">Cancellation reason</p>
            <p className="text-sm text-red-700">{ride.cancellation_reason}</p>
            {ride.cancellation_source === "system" && (
              <p className="text-xs text-red-400 mt-1">Cancelled by system</p>
            )}
          </div>
        )}

        <StartCompleteActions ride={ride} onRideUpdate={setRide} />
      </div>

      {/* History */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4">
        <h2 className="font-semibold text-gray-900">History</h2>
        <RideHistoryLog history={history} />
      </div>
    </div>
  );
}
