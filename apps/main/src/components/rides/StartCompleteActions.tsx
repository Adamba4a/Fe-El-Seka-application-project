"use client";

import { useState } from "react";
import type { RideStatus } from "@fe-el-seka/shared";

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

interface StartCompleteActionsProps {
  rideId: string;
  status: RideStatus;
  onStart: () => Promise<void>;
  onComplete: () => Promise<void>;
}

export function StartCompleteActions({
  rideId: _rideId,
  status,
  onStart,
  onComplete,
}: StartCompleteActionsProps) {
  const [startLoading, setStartLoading] = useState(false);
  const [completeLoading, setCompleteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === "completed" || status === "cancelled") return null;

  const handleStart = async () => {
    setStartLoading(true);
    setError(null);
    try {
      await onStart();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start ride.");
    } finally {
      setStartLoading(false);
    }
  };

  const handleComplete = async () => {
    setCompleteLoading(true);
    setError(null);
    try {
      await onComplete();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to complete ride.");
    } finally {
      setCompleteLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {error && (
        <p className="text-body-sm text-content-destructive">{error}</p>
      )}

      {status === "scheduled" && (
        <button
          type="button"
          onClick={handleStart}
          disabled={startLoading}
          className="w-full flex items-center justify-center gap-2 bg-brand-primary hover:bg-brand-primary-hover text-white rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
        >
          {startLoading && <Spinner />}
          {startLoading ? "Starting…" : "Start Ride"}
        </button>
      )}

      {status === "in_progress" && (
        <button
          type="button"
          onClick={handleComplete}
          disabled={completeLoading}
          className="w-full flex items-center justify-center gap-2 bg-brand-primary hover:bg-brand-primary-hover text-white rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
        >
          {completeLoading && <Spinner />}
          {completeLoading ? "Completing…" : "Complete Ride"}
        </button>
      )}
    </div>
  );
}
