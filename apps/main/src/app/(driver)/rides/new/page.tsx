"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { createRide } from "@/lib/api/rides";
import { getMyVehicle } from "@/lib/api/vehicles";
import { RideForm } from "@/components/rides/RideForm";
import { BottomSheet } from "@/components";
import { VerificationRequiredModal } from "@/components/verification/VerificationRequiredModal";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Ride, CreateRidePayload, Location, Coordinates, Locale } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("@/components/rides/RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="fixed inset-0 bg-surface-bg" /> }
);

export default function NewRidePage() {
  const t = useTranslations("driver.newRide");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdRide, setCreatedRide] = useState<Ride | null>(null);
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
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
      if (err?.error === "verification_required") {
        setVerifyModalOpen(true);
      } else {
        setError(err?.message ?? t("postFailed"));
      }
    } finally {
      setLoading(false);
    }
  };

  if (createdRide) {
    return (
      <div className="fixed inset-0 z-50 bg-surface-bg flex items-center justify-center p-6">
        <div className="bg-surface-card border border-border-default rounded-2xl p-6 w-full max-w-sm space-y-4">
          <h2 className="text-h3 text-content-primary">{t("postedTitle")}</h2>
          <p className="text-sm text-content-muted">{t("postedBody")}</p>
          <div className="flex justify-between items-center py-3 border-t border-b border-border-default">
            <span className="text-sm text-content-secondary">{t("farePerSeatLabel")}</span>
            <span className="text-base font-semibold text-content-primary">
              {formatCurrency(Number(createdRide.price_per_seat), locale)}
            </span>
          </div>
          <p className="text-xs text-content-muted">
            {t("fareNote")}
          </p>
          <button
            type="button"
            onClick={() => router.push(`/rides/${createdRide.id}/manage`)}
            className="w-full bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
          >
            {t("viewRide")}
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
      <VerificationRequiredModal
        isOpen={verifyModalOpen}
        onClose={() => setVerifyModalOpen(false)}
        role="driver"
      />

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
                {selecting === "origin" ? t("tapMapToSetOrigin") : t("tapMapToSetDestination")}
              </p>
              {origin && selecting === "destination" && (
                <p className="text-caption text-content-muted truncate">{t("originPrefix")} {origin.address}</p>
              )}
            </>
          ) : (
            <p className="text-label text-content-primary">{t("tapMapToExplore")}</p>
          )}
          <button type="button" onClick={handleBackToForm} className="text-body-sm text-brand-primary">
            {t("backToForm")}
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
              <span className="inline-block rtl:rotate-180">←</span>
            </button>
            <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
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
