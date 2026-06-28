"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { createClient } from "../../../../../lib/supabase/client";
import { useSession } from "../../../../../lib/auth/hooks";
import { useDriverLocation } from "../../../../../lib/hooks/useDriverLocation";
import { LiveTrackingMap } from "../../../../../components/tracking/LiveTrackingMap";
import { TrackingStatusBanner } from "../../../../../components/tracking/TrackingStatusBanner";

const supabase = createClient();

export default function TrackingPage() {
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
      .eq("status", "confirmed")
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
    router.replace(`/(passenger)/bookings/${bookingId}`);
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-screen text-content-secondary">
        Loading…
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="flex items-center justify-center h-screen text-content-secondary">
        You do not have a confirmed booking for this ride.
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
        {locationError && !location ? (
          <div className="flex items-center justify-center h-full text-content-secondary text-sm">
            Location unavailable — driver has not started sharing yet.
          </div>
        ) : (
          <LiveTrackingMap location={location} isStale={isStale} />
        )}
      </div>
    </div>
  );
}
