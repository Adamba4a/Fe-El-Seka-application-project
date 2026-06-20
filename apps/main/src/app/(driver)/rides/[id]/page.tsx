"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getRide, startRide, completeRide, cancelRide } from "@/lib/api/rides";
import { RideStatusBadge } from "@/components/rides/RideStatusBadge";
import { RideHistoryLog } from "@/components/rides/RideHistoryLog";
import { StartCompleteActions } from "@/components/rides/StartCompleteActions";
import { BottomSheet, Spinner } from "@/components";
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

  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

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
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-surface-bg rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (error || !ride) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-body-sm text-content-secondary">{error ?? "Ride not found."}</p>
        <Link href="/rides" className="text-body-sm text-brand-primary underline">← Back to My Rides</Link>
      </div>
    );
  }

  // ride: Ride (narrowed — safe to use in closures below)
  const handleStart = async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const updated = await startRide(session.access_token, ride.id);
    setRide(updated);
  };

  const handleComplete = async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const updated = await completeRide(session.access_token, ride.id);
    setRide(updated);
  };

  const handleCancel = async () => {
    setCancelLoading(true);
    setCancelError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const updated = await cancelRide(session.access_token, ride.id, { reason: cancelReason });
      setRide(updated);
      setIsCancelOpen(false);
      setCancelReason("");
    } catch (err: any) {
      setCancelError(err?.detail?.message ?? "Failed to cancel ride.");
    } finally {
      setCancelLoading(false);
    }
  };

  const closeCancelSheet = () => {
    setIsCancelOpen(false);
    setCancelReason("");
    setCancelError(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/rides" className="text-content-muted hover:text-content-secondary">←</Link>
        <h1 className="text-h3 text-content-primary">Ride Detail</h1>
      </div>

      {/* Status + actions card */}
      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <RideStatusBadge status={ride.status} />
          {ride.status === "scheduled" && (
            <Link
              href={`/rides/${ride.id}/edit`}
              className="text-body-sm text-brand-primary font-medium hover:underline"
            >
              Edit
            </Link>
          )}
        </div>

        <div className="space-y-2">
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">From</p>
            <p className="text-body-sm font-medium text-content-primary">{ride.origin.address}</p>
          </div>
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">To</p>
            <p className="text-body-sm font-medium text-content-primary">{ride.destination.address}</p>
          </div>
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">Departure</p>
            <p className="text-body-sm font-medium text-content-primary">{formatDate(ride.departure_datetime)}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border-default">
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">{ride.available_seats}</p>
            <p className="text-caption text-content-muted">Available</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">{ride.total_seats}</p>
            <p className="text-caption text-content-muted">Total</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">EGP {ride.price_per_seat}</p>
            <p className="text-caption text-content-muted">/seat</p>
          </div>
        </div>

        {ride.notes && (
          <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
            {ride.notes}
          </p>
        )}

        {ride.cancellation_reason && (
          <div className="bg-status-cancelled-bg rounded-xl px-3 py-2 space-y-1">
            <p className="text-caption text-content-destructive uppercase tracking-wide">Cancellation reason</p>
            <p className="text-body-sm text-content-destructive">{ride.cancellation_reason}</p>
            {ride.cancellation_source === "system" && (
              <p className="text-caption text-content-muted mt-1">Cancelled by system</p>
            )}
          </div>
        )}

        <StartCompleteActions
          rideId={ride.id}
          status={ride.status}
          onStart={handleStart}
          onComplete={handleComplete}
        />

        {ride.status === "scheduled" && (
          <button
            type="button"
            onClick={() => setIsCancelOpen(true)}
            className="w-full py-3 px-4 border border-border-default rounded-xl text-body-sm text-content-destructive font-medium hover:bg-status-cancelled-bg transition-colors"
          >
            Cancel Ride
          </button>
        )}
      </div>

      {/* History */}
      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <h2 className="font-semibold text-content-primary">History</h2>
        <RideHistoryLog entries={history} />
      </div>

      {/* Cancel ride bottom sheet */}
      <BottomSheet isOpen={isCancelOpen} onClose={closeCancelSheet}>
        <div className="space-y-4">
          <h2 className="text-h3 text-content-primary">Cancel Ride</h2>
          <p className="text-body-sm text-content-muted">
            Please provide a reason for cancellation. Your passengers will be notified.
          </p>
          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
            placeholder="e.g. Car broke down, emergency…"
            className="w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus resize-none transition-colors"
          />
          {cancelError && (
            <p className="text-caption text-content-destructive">{cancelError}</p>
          )}
          <button
            type="button"
            onClick={handleCancel}
            disabled={!cancelReason.trim() || cancelLoading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-surface-destructive text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {cancelLoading && <Spinner />}
            {cancelLoading ? "Cancelling…" : "Confirm Cancellation"}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
