"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { getRide, startRide, completeRide, cancelRide } from "@/lib/api/rides";
import { reportLocation } from "@/lib/api/location";
import { RideStatusBadge } from "@/components/rides/RideStatusBadge";
import { RideHistoryLog } from "@/components/rides/RideHistoryLog";
import { StartCompleteActions } from "@/components/rides/StartCompleteActions";
import { BottomSheet, Spinner } from "@/components";
import type { Ride, RideHistoryEntry } from "@fe-el-seka/shared";

const RideDetailMap = dynamic(
  () => import("@/components/bookings/RideDetailMap").then((m) => ({ default: m.RideDetailMap })),
  { ssr: false, loading: () => <div className="w-full h-56 bg-surface-bg rounded-xl animate-pulse" /> }
);

function bearingDeg(from: GeolocationPosition, to: GeolocationPosition): number {
  const lat1 = (from.coords.latitude * Math.PI) / 180;
  const lat2 = (to.coords.latitude * Math.PI) / 180;
  const dLng = ((to.coords.longitude - from.coords.longitude) * Math.PI) / 180;
  const y = Math.sin(dLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RideManagePage() {
  const t = useTranslations("driver.manage");
  const tEditRide = useTranslations("driver.editRide");
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ride, setRide] = useState<Ride | null>(null);
  const [history, setHistory] = useState<RideHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const lastPosRef = useRef<GeolocationPosition | null>(null);
  const lastSentRef = useRef<number>(0);

  useEffect(() => {
    const load = async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        const detail = await getRide(session.access_token, id);
        setRide(detail.ride);
        setHistory(detail.history);
      } catch (err: any) {
        setError(err?.detail?.message ?? err?.message ?? tEditRide("loadFailed"));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  // GPS location broadcasting when ride is in_progress
  useEffect(() => {
    if (ride?.status !== "in_progress") return;
    if (typeof navigator === "undefined" || !navigator.geolocation) return;

    const INTERVAL_MS = 10_000;

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const now = Date.now();
        if (now - lastSentRef.current < INTERVAL_MS) return;
        lastSentRef.current = now;

        const bearing = lastPosRef.current ? bearingDeg(lastPosRef.current, pos) : null;
        lastPosRef.current = pos;

        (async () => {
          const supabase = createClient();
          const { data: { session } } = await supabase.auth.getSession();
          if (!session) return;
          try {
            await reportLocation(session.access_token, ride.id, {
              lat: pos.coords.latitude,
              lng: pos.coords.longitude,
              bearing,
              speed_kmh: pos.coords.speed != null ? pos.coords.speed * 3.6 : null,
              client_timestamp: new Date(pos.timestamp).toISOString(),
            });
            setGpsError(null);
          } catch {
            // silent — don't interrupt the driver UI on transient errors
          }
        })();
      },
      (err) => setGpsError(err.message),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [ride?.status, ride?.id]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-surface-bg rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (error || !ride) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-body-sm text-content-secondary">{error ?? t("notFoundTitle")}</p>
        <Link href="/rides" className="text-body-sm text-brand-primary underline">{t("backToMyRides")}</Link>
      </div>
    );
  }

  const handleStart = async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const updated = await startRide(session.access_token, ride.id);
    setRide(updated);
  };

  const handleComplete = async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const updated = await completeRide(session.access_token, ride.id);
    setRide(updated);
  };

  const handleCancel = async () => {
    setCancelLoading(true);
    setCancelError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const updated = await cancelRide(session.access_token, ride.id, { reason: cancelReason });
      setRide(updated);
      setIsCancelOpen(false);
      setCancelReason("");
    } catch (err: any) {
      setCancelError(err?.detail?.message ?? t("cancelError"));
    } finally {
      setCancelLoading(false);
    }
  };

  const closeCancelSheet = () => {
    setIsCancelOpen(false);
    setCancelReason("");
    setCancelError(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/rides" className="text-content-muted hover:text-content-secondary">
          <span className="inline-block rtl:rotate-180">←</span>
        </Link>
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
      </div>

      {/* Status + actions card */}
      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <RideStatusBadge status={ride.status} />
          <div className="flex items-center gap-3">
            <Link
              href={`/rides/${ride.id}/bookings`}
              className="text-body-sm text-brand-primary font-medium hover:underline"
            >
              {t("bookings")}
            </Link>
            {ride.status === "scheduled" && (
              <Link
                href={`/rides/${ride.id}/edit`}
                className="text-body-sm text-brand-primary font-medium hover:underline"
              >
                {t("edit")}
              </Link>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">{t("from")}</p>
            <p className="text-body-sm font-medium text-content-primary">{ride.origin.address}</p>
          </div>
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">{t("to")}</p>
            <p className="text-body-sm font-medium text-content-primary">{ride.destination.address}</p>
          </div>
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">{t("departure")}</p>
            <p className="text-body-sm font-medium text-content-primary">{formatDate(ride.departure_datetime)}</p>
          </div>
        </div>

        <RideDetailMap
          routeGeometry={ride.route_geometry}
          boardingPoint={null}
          alightingPoint={null}
          origin={ride.origin.coordinates}
          destination={ride.destination.coordinates}
        />

        <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border-default">
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">{ride.available_seats}</p>
            <p className="text-caption text-content-muted">{t("available")}</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">{ride.total_seats}</p>
            <p className="text-caption text-content-muted">{t("total")}</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-content-primary">EGP {ride.price_per_seat}</p>
            <p className="text-caption text-content-muted">{t("perSeat")}</p>
          </div>
        </div>

        {ride.notes && (
          <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
            {ride.notes}
          </p>
        )}

        {ride.cancellation_reason && (
          <div className="bg-status-cancelled-bg rounded-xl px-3 py-2 space-y-1">
            <p className="text-caption text-content-destructive uppercase tracking-wide">{t("cancellationReason")}</p>
            <p className="text-body-sm text-content-destructive">{ride.cancellation_reason}</p>
            {ride.cancellation_source === "system" && (
              <p className="text-caption text-content-muted mt-1">{t("cancelledBySystem")}</p>
            )}
          </div>
        )}

        {ride.status === "in_progress" && (
          <div className={`rounded-xl px-3 py-2 text-xs font-medium ${gpsError ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>
            {gpsError ? t("gpsErrorPrefix", { error: gpsError }) : t("broadcastingLocation")}
          </div>
        )}

        <StartCompleteActions
          rideId={ride.id}
          status={ride.status}
          onStart={handleStart}
          onComplete={handleComplete}
        />

        {ride.status === "scheduled" && (
          <button
            type="button"
            onClick={() => setIsCancelOpen(true)}
            className="w-full py-3 px-4 border border-border-default rounded-xl text-body-sm text-content-destructive font-medium hover:bg-status-cancelled-bg transition-colors"
          >
            {t("cancelRide")}
          </button>
        )}
      </div>

      {/* History */}
      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <h2 className="font-semibold text-content-primary">{t("history")}</h2>
        <RideHistoryLog entries={history} />
      </div>

      {/* Cancel ride bottom sheet */}
      <BottomSheet isOpen={isCancelOpen} onClose={closeCancelSheet}>
        <div className="space-y-4">
          <h2 className="text-h3 text-content-primary">{t("cancelSheetTitle")}</h2>
          <p className="text-body-sm text-content-muted">
            {t("cancelSheetBody")}
          </p>
          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
            placeholder={t("cancelReasonPlaceholder")}
            className="w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus resize-none transition-colors"
          />
          {cancelError && (
            <p className="text-caption text-content-destructive">{cancelError}</p>
          )}
          <button
            type="button"
            onClick={handleCancel}
            disabled={!cancelReason.trim() || cancelLoading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-surface-destructive text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {cancelLoading && <Spinner />}
            {cancelLoading ? t("cancelling") : t("confirmCancellation")}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
