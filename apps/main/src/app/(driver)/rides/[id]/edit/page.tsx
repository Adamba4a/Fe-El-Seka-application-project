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
      router.push(`/rides/${id}`);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setSubmitError(detail?.message ?? "Failed to save changes.");
    } finally {
      setLoading(false);
    }
  };

  if (fetchError) {
    return <p className="text-sm text-red-600 p-4">{fetchError}</p>;
  }

  if (!ride) {
    return <div className="h-48 bg-gray-100 rounded-xl animate-pulse m-4" />;
  }

  if (ride.status !== "scheduled") {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Only scheduled rides can be edited.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="text-gray-500 hover:text-gray-700">←</button>
        <h1 className="text-xl font-bold text-gray-900">Edit Ride</h1>
      </div>

      <RideForm
        mode="edit"
        initialValues={{
          origin: ride.origin,
          destination: ride.destination,
          departure_datetime: ride.departure_datetime,
          total_seats: ride.total_seats,
          price_per_seat: ride.price_per_seat,
          notes: ride.notes ?? "",
        }}
        loading={loading}
        error={submitError}
        onSubmit={handleSubmit as any}
      />
    </div>
  );
}
