"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { BottomSheet } from "@/components";
import type { Location, Coordinates } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("@/components/rides/RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="fixed inset-0 bg-surface-bg" /> }
);

type GeoState = "idle" | "loading" | "granted" | "denied";
type Selecting = "pickup" | "dropoff" | null;

export default function BookRidePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const departureAt = searchParams.get("departure_at");

  const [geoState, setGeoState] = useState<GeoState>("loading");
  const [pickup, setPickup] = useState<Location | undefined>();
  const [dropoff, setDropoff] = useState<Location | undefined>();
  const [selecting, setSelecting] = useState<Selecting>(null);
  const [sheetOpen, setSheetOpen] = useState(true);

  useEffect(() => {
    if (!navigator.geolocation) {
      setGeoState("denied");
      return;
    }
    setGeoState("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoState("granted");
        // GPS-prefilled so the common case skips a pin-drop step entirely —
        // the passenger can still override via "Change" below.
        setPickup({
          coordinates: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          address: "Current location",
        });
      },
      () => setGeoState("denied"),
      { timeout: 8000 }
    );
  }, []);

  const handlePinDrop = (coords: Coordinates, address: string) => {
    const loc: Location = { coordinates: coords, address };
    if (selecting === "pickup") {
      setPickup(loc);
    } else if (selecting === "dropoff") {
      setDropoff(loc);
    }
    setSelecting(null);
    setSheetOpen(true);
  };

  const handleRequestPickupMap = () => {
    setSheetOpen(false);
    setSelecting("pickup");
  };

  const handleRequestDropoffMap = () => {
    setSheetOpen(false);
    setSelecting("dropoff");
  };

  const handleConfirm = () => {
    if (!pickup || !dropoff) return;
    const params = new URLSearchParams({
      origin_lat: String(pickup.coordinates.lat),
      origin_lng: String(pickup.coordinates.lng),
      dest_lat: String(dropoff.coordinates.lat),
      dest_lng: String(dropoff.coordinates.lng),
      ...(departureAt ? { departure_at: departureAt } : {}),
    });
    router.push(`/rides/${id}?${params}`);
  };

  return (
    <>
      <div className="fixed inset-0 z-20">
        <RideMap onPinDrop={handlePinDrop} fullScreen />
      </div>

      {!sheetOpen && selecting && (
        <div className="fixed top-4 left-4 right-4 z-30 bg-surface-card border border-border-default rounded-xl px-4 py-3 shadow-sm">
          <p className="text-label text-content-primary">
            {selecting === "pickup" ? "📍 Tap map to set pickup" : "📍 Tap map to set dropoff"}
          </p>
        </div>
      )}

      <BottomSheet isOpen={sheetOpen} onClose={() => setSheetOpen(false)} maxHeightPercent={60}>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="text-content-muted hover:text-content-secondary"
            >
              ←
            </button>
            <div>
              <h1 className="text-h3 text-content-primary">Pickup &amp; Dropoff</h1>
              <p className="text-sm text-content-muted mt-1">
                We use your current location for pickup unless you change it.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between p-3 rounded-xl border border-border-default bg-surface-card">
              <div className="min-w-0">
                <p className="text-caption text-content-muted">Pickup</p>
                <p className="text-body-sm text-content-primary truncate">
                  {geoState === "loading" && !pickup
                    ? "Getting your location…"
                    : (pickup?.address ?? "Not set")}
                </p>
              </div>
              <button
                type="button"
                onClick={handleRequestPickupMap}
                className="text-body-sm text-brand-primary shrink-0 ml-2"
              >
                {pickup ? "Change" : "Set on map"}
              </button>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl border border-border-default bg-surface-card">
              <div className="min-w-0">
                <p className="text-caption text-content-muted">Dropoff</p>
                <p className="text-body-sm text-content-primary truncate">
                  {dropoff?.address ?? "Tap to set on map"}
                </p>
              </div>
              <button
                type="button"
                onClick={handleRequestDropoffMap}
                className="text-body-sm text-brand-primary shrink-0 ml-2"
              >
                {dropoff ? "Change" : "Set on map"}
              </button>
            </div>
          </div>

          <button
            type="button"
            disabled={!pickup || !dropoff}
            onClick={handleConfirm}
            className="w-full bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-3 font-medium disabled:opacity-50 transition-colors"
          >
            Confirm
          </button>
        </div>
      </BottomSheet>
    </>
  );
}
