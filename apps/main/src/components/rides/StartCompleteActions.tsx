"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Ride } from "@fe-el-seka/shared";
import { createClient } from "@/lib/supabase/client";
import { cancelRide, startRide, completeRide } from "@/lib/api/rides";

async function getToken(): Promise<string> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");
  return session.access_token;
}

// ─────────────────────────────────────────────────────────────────────────────
// Cancel Modal (T035)
// ─────────────────────────────────────────────────────────────────────────────

function CancelRideModal({
  rideId,
  onCancelled,
  onClose,
}: {
  rideId: string;
  onCancelled: (ride: Ride) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!reason.trim()) {
      setError("A cancellation reason is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const updated = await cancelRide(token, rideId, { reason: reason.trim() });
      onCancelled(updated);
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to cancel ride.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Cancel Ride</h2>
        <p className="text-sm text-gray-600">Please provide a reason for cancelling this ride.</p>

        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder="e.g. Change of plans"
          className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Keep Ride
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading}
            className="flex-1 bg-red-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? "Cancelling…" : "Cancel Ride"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Start / Complete / Cancel action buttons (T050)
// ─────────────────────────────────────────────────────────────────────────────

export function StartCompleteActions({
  ride,
  onRideUpdate,
}: {
  ride: Ride;
  onRideUpdate: (updated: Ride) => void;
}) {
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canStart =
    ride.status === "scheduled" &&
    new Date() >= new Date(ride.departure_datetime);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const updated = await startRide(token, ride.id);
      onRideUpdate(updated);
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to start ride.");
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const updated = await completeRide(token, ride.id);
      onRideUpdate(updated);
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to complete ride.");
    } finally {
      setLoading(false);
    }
  };

  if (ride.status === "completed" || ride.status === "cancelled") {
    return null;
  }

  return (
    <>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex flex-col gap-3">
        {ride.status === "scheduled" && (
          <>
            <button
              type="button"
              onClick={handleStart}
              disabled={loading || !canStart}
              title={!canStart ? "Available at departure time" : undefined}
              className="w-full bg-blue-600 text-white rounded-xl py-3 font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors"
            >
              {loading ? "Starting…" : "Start Ride"}
            </button>
            {!canStart && (
              <p className="text-xs text-gray-400 text-center">
                Start button unlocks at departure time
              </p>
            )}
            <button
              type="button"
              onClick={() => setShowCancelModal(true)}
              className="w-full border border-red-300 text-red-600 rounded-xl py-3 font-medium hover:bg-red-50 transition-colors"
            >
              Cancel Ride
            </button>
          </>
        )}

        {ride.status === "in_progress" && (
          <button
            type="button"
            onClick={handleComplete}
            disabled={loading}
            className="w-full bg-green-600 text-white rounded-xl py-3 font-medium disabled:opacity-50 hover:bg-green-700 transition-colors"
          >
            {loading ? "Completing…" : "Complete Ride"}
          </button>
        )}
      </div>

      {showCancelModal && (
        <CancelRideModal
          rideId={ride.id}
          onCancelled={(updated) => {
            setShowCancelModal(false);
            onRideUpdate(updated);
          }}
          onClose={() => setShowCancelModal(false)}
        />
      )}
    </>
  );
}
