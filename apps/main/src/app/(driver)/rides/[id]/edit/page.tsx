"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { getRide, editRide } from "@/lib/api/rides";
import { RideForm } from "@/components/rides/RideForm";
import type { Ride, EditRidePayload } from "@fe-el-seka/shared";

export default function EditRidePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ride, setRide] = useState<Ride | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        const detail = await getRide(session.access_token, id);
        setRide(detail.ride);
      } catch (err: any) {
        setFetchError(err?.detail?.message ?? "Failed to load ride.");
      }
    };
    load();
  }, [id]);

  const handleSubmit = async (payload: EditRidePayload) => {
    setLoading(true);
    setSubmitError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      await editRide(session.access_token, id, payload);
      router.push(`/rides/${id}/manage`);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setSubmitError(detail?.message ?? "Failed to save changes.");
    } finally {
      setLoading(false);
    }
  };

  if (fetchError) {
    return <p className="text-body-sm text-content-destructive p-4">{fetchError}</p>;
  }

  if (!ride) {
    return <div className="h-48 bg-surface-bg rounded-xl animate-pulse m-4" />;
  }

  if (ride.status !== "scheduled") {
    return (
      <div className="text-center py-12">
        <p className="text-body-sm text-content-secondary">Only scheduled rides can be edited.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          ←
        </button>
        <h1 className="text-h3 text-content-primary">Edit Ride</h1>
      </div>

      {isDirty && (
        <div className="bg-status-in-progress-bg border border-border-default rounded-xl px-4 py-3 flex items-center gap-2">
          <svg
            className="w-4 h-4 text-status-in-progress flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
          <p className="text-body-sm text-status-in-progress font-medium">Unsaved changes</p>
        </div>
      )}

      <RideForm
        mode="edit"
        initialValues={{
          origin: ride.origin,
          destination: ride.destination,
          departure_datetime: ride.departure_datetime,
          total_seats: ride.total_seats,
          notes: ride.notes ?? "",
        }}
        loading={loading}
        error={submitError}
        onSubmit={handleSubmit as any}
        onDirtyChange={setIsDirty}
      />
    </div>
  );
}
