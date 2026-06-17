"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { createRide } from "@/lib/api/rides";
import { getMyVehicle } from "@/lib/api/vehicles";
import { RideForm } from "@/components/rides/RideForm";
import type { CreateRidePayload } from "@fe-el-seka/shared";

export default function NewRidePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vehicleChecked, setVehicleChecked] = useState(false);

  useEffect(() => {
    const checkVehicle = async () => {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      try {
        await getMyVehicle(session.access_token);
        setVehicleChecked(true);
      } catch {
        router.replace("/driver/register-vehicle");
      }
    };
    checkVehicle();
  }, [router]);

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
      router.push(`/rides/${ride.id}`);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setError(detail?.message ?? "Failed to post ride. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (!vehicleChecked) {
    return <div className="h-48 bg-gray-100 rounded-xl animate-pulse m-4" />;
  }

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
