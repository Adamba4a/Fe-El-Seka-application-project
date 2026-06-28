"use client";

import { useEffect, useRef, useState } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { createClient } from "../supabase/client";
import { getDriverLocation } from "../api/location";
import type { DriverLocationData } from "../api/location";

const supabase = createClient();

export function useDriverLocation(rideId: string, token: string) {
  const [location, setLocation] = useState<DriverLocationData | null>(null);
  const [isStale, setIsStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const channelRef = useRef<RealtimeChannel | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function refreshStaleTimer(updatedAt: string) {
    if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
    setIsStale(false);
    const age = Date.now() - new Date(updatedAt).getTime();
    const remaining = Math.max(0, 60_000 - age);
    staleTimerRef.current = setTimeout(() => setIsStale(true), remaining);
  }

  useEffect(() => {
    let cancelled = false;

    getDriverLocation(token, rideId)
      .then((loc) => {
        if (cancelled) return;
        if (loc) {
          setLocation(loc);
          refreshStaleTimer(loc.updatedAt);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load driver location.");
      });

    channelRef.current = supabase
      .channel(`driver-location-${rideId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "driver_locations",
          filter: `ride_id=eq.${rideId}`,
        },
        async () => {
          // Re-fetch via API: the raw Realtime payload carries PostGIS binary,
          // not float lat/lng; driver_locations_view resolves that server-side.
          const loc = await getDriverLocation(token, rideId).catch(() => null);
          if (cancelled || !loc) return;
          setLocation(loc);
          refreshStaleTimer(loc.updatedAt);
          setError(null);
        }
      )
      .subscribe();

    return () => {
      cancelled = true;
      if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [rideId, token]); // eslint-disable-line react-hooks/exhaustive-deps

  return { location, isStale, error };
}
