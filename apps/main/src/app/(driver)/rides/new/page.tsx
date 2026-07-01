"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { createClient } from "@/lib/supabase/client";
import { createRide } from "@/lib/api/rides";
import { getMyVehicle } from "@/lib/api/vehicles";
import { RideForm } from "@/components/rides/RideForm";
import { BottomSheet } from "@/components";
import type { Ride, CreateRidePayload, Location, Coordinates } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("@/components/rides/RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="fixed inset-0 bg-surface-bg" /> }
);

export default function NewRidePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdRide, setCreatedRide] = useState<Ride | null>(null);
  const [vehicleChecked, setVehicleChecked] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(true);
  const [origin, setOrigin] = useState<Location | undefined>();
  const [destination, setDestination] = useState<Location | undefined>();
  const [selecting, setSelecting] = useState<"origin" | "destination" | null>(null);

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

  const handlePinDrop = (coords: Coordinates, address: string) => {
    const loc: Location = { coordinates: coords, address };
    if (selecting === "origin") {
      setOrigin(loc);
      setSelecting("destination"); // Auto-advance to destination
    } else if (selecting === "destination") {
      setDestination(loc);
      setSelecting(null);
      setSheetOpen(true); // Reopen form after destination is placed
    }
  };

  const handleRequestOriginMap = () => {
    setSheetOpen(false);
    setSelecting("origin");
  };

  const handleRequestDestinationMap = () => {
    setSheetOpen(false);
    setSelecting("destination");
  };

  const handleBackToForm = () => {
    setSheetOpen(true);
    setSelecting(null);
  };

  const handleSubmit = async (payload: CreateRidePayload) => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const ride = await createRide(session.access_token, payload);
      setCreatedRide(ride);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setError(detail?.message ?? "Failed to post ride. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (createdRide) {
    return (
      <div className="fixed inset-0 z-50 bg-surface-bg flex items-center justify-center p-6">
        <div className="bg-surface-card border border-border-default rounded-2xl p-6 w-full max-w-sm space-y-4">
          <h2 className="text-h3 text-content-primary">Ride Posted!</h2>
          <p className="text-sm text-content-muted">Your ride has been created successfully.</p>
          <div className="flex justify-between items-center py-3 border-t border-b border-border-default">
            <span className="text-sm text-content-secondary">Fare per seat</span>
            <span className="text-base font-semibold text-content-primary">
              EGP {createdRide.price_per_seat}
            </span>
          </div>
          <p className="text-xs text-content-muted">
            This fare is set by our system based on your route and current conditions.
          </p>
          <button
            type="button"
            onClick={() => router.push(`/rides/${createdRide.id}/manage`)}
            className="w-full bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium transition-colors"
          >
            View Ride
          </button>
        </div>
      </div>
    );
  }

  if (!vehicleChecked) {
    return (
      <div className="fixed inset-0 z-20 bg-surface-bg flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <>
      {/* Full-screen Leaflet map — always rendered behind the BottomSheet */}
      <div className="fixed inset-0 z-20">
        <RideMap onPinDrop={handlePinDrop} fullScreen />
      </div>

      {/* Overlay — always visible when sheet is closed so the user can always return */}
      {!sheetOpen && (
        <div className="fixed top-4 left-4 right-4 z-30 bg-surface-card border border-border-default rounded-xl px-4 py-3 space-y-1.5 shadow-sm">
          {selecting ? (
            <>
              <p className="text-label text-content-primary">
                {selecting === "origin" ? "📍 Tap map to set origin" : "📍 Tap map to set destination"}
              </p>
              {origin && selecting === "destination" && (
                <p className="text-caption text-content-muted truncate">Origin: {origin.address}</p>
              )}
            </>
          ) : (
            <p className="text-label text-content-primary">Tap map to explore or open the form</p>
          )}
          <button type="button" onClick={handleBackToForm} className="text-body-sm text-brand-primary">
            ← Back to form
          </button>
        </div>
      )}

      {/* BottomSheet containing the ride creation form */}
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
            externalOrigin={origin}
            externalDestination={destination}
            onRequestOriginMap={handleRequestOriginMap}
            onRequestDestinationMap={handleRequestDestinationMap}
          />
        </div>
      </BottomSheet>
    </>
  );
}
