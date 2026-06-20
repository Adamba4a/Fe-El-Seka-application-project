"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { createRide } from "@/lib/api/rides";
import { getMyVehicle } from "@/lib/api/vehicles";
import { RideForm } from "@/components/rides/RideForm";
import { BottomSheet } from "@/components";
import type { CreateRidePayload } from "@fe-el-seka/shared";

export default function NewRidePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vehicleChecked, setVehicleChecked] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(true);

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
      if (!session) { router.push("/login"); return; }
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
    return (
      <div className="fixed inset-0 z-20 bg-surface-bg flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <>
      {/* Full-screen map background — tap to reopen the form sheet */}
      <div
        className="fixed inset-0 z-20 bg-surface-bg flex flex-col items-center justify-center gap-3 cursor-pointer"
        onClick={() => setSheetOpen(true)}
      >
        <svg
          className="w-12 h-12 text-content-muted"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        {!sheetOpen && (
          <p className="text-body-sm text-content-muted">Tap to open form</p>
        )}
      </div>

      {/* BottomSheet with ride creation form */}
      <BottomSheet isOpen={sheetOpen} onClose={() => setSheetOpen(false)} maxHeightPercent={80}>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="text-content-muted hover:text-content-secondary"
            >
              ←
            </button>
            <h1 className="text-h3 text-content-primary">Post a Ride</h1>
          </div>

          <RideForm
            mode="create"
            loading={loading}
            error={error}
            onSubmit={handleSubmit as any}
          />
        </div>
      </BottomSheet>
    </>
  );
}
