"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { createClient } from "../../../../../lib/supabase/client";
import { useSession } from "../../../../../lib/auth/hooks";
import { useDriverLocation } from "../../../../../lib/hooks/useDriverLocation";
import { LiveTrackingMap } from "../../../../../components/tracking/LiveTrackingMap";
import { TrackingStatusBanner } from "../../../../../components/tracking/TrackingStatusBanner";

const supabase = createClient();

export default function TrackingPage() {
  const t = useTranslations("passenger.tracking");
  const tc = useTranslations("common");
  const { id: rideId } = useParams<{ id: string }>();
  const router = useRouter();
  const session = useSession();

  const [bookingId, setBookingId] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);
  const [rideCompleted, setRideCompleted] = useState(false);
  const bookingChannelRef = useRef<RealtimeChannel | null>(null);

  const token = session?.access_token ?? "";
  const { location, isStale, error: locationError } = useDriverLocation(
    rideId,
    token
  );

  // Verify session + confirmed booking on mount
  useEffect(() => {
    if (!session) return;
    const userId = session.user.id;

    supabase
      .from("bookings")
      .select("id, status")
      .eq("ride_id", rideId)
      .eq("passenger_id", userId)
      .in("status", ["confirmed", "completed"])
      .maybeSingle()
      .then(({ data }) => {
        if (!data) {
          setAccessDenied(true);
        } else {
          setBookingId(data.id);
        }
      });
  }, [session, rideId]);

  // Subscribe to booking status changes once bookingId is known
  useEffect(() => {
    if (!bookingId) return;

    bookingChannelRef.current = supabase
      .channel(`booking-status-${bookingId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "bookings",
          filter: `id=eq.${bookingId}`,
        },
        (payload) => {
          if ((payload.new as { status?: string }).status === "completed") {
            setRideCompleted(true);
          }
        }
      )
      .subscribe();

    return () => {
      if (bookingChannelRef.current) {
        supabase.removeChannel(bookingChannelRef.current);
        bookingChannelRef.current = null;
      }
    };
  }, [bookingId]);

  function handleRedirect() {
    router.replace(`/bookings/${bookingId}`);
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-screen text-content-secondary">
        {t("loading")}
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex items-start p-4">
          <button
            type="button"
            onClick={() => router.back()}
            aria-label={tc("back")}
            className="text-content-muted hover:text-content-secondary text-lg"
          >
            <span className="inline-block rtl:rotate-180">←</span>
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center text-content-secondary">
          {t("accessDenied")}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <TrackingStatusBanner
        isStale={isStale}
        rideCompleted={rideCompleted}
        onRedirectComplete={handleRedirect}
      />

      <div className="flex-1 relative">
        <LiveTrackingMap location={location} isStale={isStale} />

        <button
          type="button"
          onClick={() => router.back()}
          aria-label={tc("back")}
          className="absolute top-4 start-4 z-20 h-10 w-10 flex items-center justify-center rounded-full bg-surface-card shadow-lg text-content-primary text-lg"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>

        {/* Overlay while waiting for first location fix */}
        {!location && !locationError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/30 z-10">
            <div className="bg-surface-card rounded-2xl px-6 py-4 shadow-lg text-center space-y-1">
              <p className="text-sm font-semibold text-content-primary">{t("waitingForDriver")}</p>
              <p className="text-xs text-content-muted">{t("waitingForDriverBody")}</p>
            </div>
          </div>
        )}

        {locationError && !location && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 z-10">
            <div className="bg-surface-card rounded-2xl px-6 py-4 shadow-lg text-center">
              <p className="text-sm text-content-secondary">{t("locationUnavailable")}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
