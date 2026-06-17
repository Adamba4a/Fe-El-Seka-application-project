"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { createRide } from "@/lib/api/rides";
import { RideForm } from "@/components/rides/RideForm";
import type { CreateRidePayload } from "@fe-el-seka/shared";

export default function NewRidePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (payload: CreateRidePayload) => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login");
        return;
      }
      const ride = await createRide(session.access_token, payload);
      router.push(`/driver/rides/${ride.id}`);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setError(detail?.message ?? "Failed to post ride. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="text-gray-500 hover:text-gray-700">
          ←
        </button>
        <h1 className="text-xl font-bold text-gray-900">Post a Ride</h1>
      </div>

      <RideForm
        mode="create"
        loading={loading}
        error={error}
        onSubmit={handleSubmit as any}
      />
    </div>
  );
}
