"use client";

import { useEffect, useRef, useState } from "react";
import type { RealtimeChannel, RealtimePostgresChangesPayload } from "@supabase/supabase-js";
import { createClient } from "../supabase/client";

export type BookingRow = Record<string, unknown>;

export interface BookingStatusFilter {
  passengerId?: string;
  bookingId?: string;
  rideId?: string;
}

const supabase = createClient();

export function useBookingStatus(filter: BookingStatusFilter) {
  const [lastEvent, setLastEvent] = useState<RealtimePostgresChangesPayload<BookingRow> | null>(null);
  const channelRef = useRef<RealtimeChannel | null>(null);

  const { bookingId, rideId, passengerId } = filter;

  useEffect(() => {
    // Build the most specific filter expression available
    let filterExpr: string | undefined;
    if (bookingId) {
      filterExpr = `id=eq.${bookingId}`;
    } else if (rideId) {
      filterExpr = `ride_id=eq.${rideId}`;
    } else if (passengerId) {
      filterExpr = `passenger_id=eq.${passengerId}`;
    }

    const key = bookingId ?? rideId ?? passengerId ?? "global";

    channelRef.current = supabase
      .channel(`booking-status-${key}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "bookings",
          filter: filterExpr,
        },
        (payload) => setLastEvent(payload as RealtimePostgresChangesPayload<BookingRow>)
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "bookings",
          filter: filterExpr,
        },
        (payload) => setLastEvent(payload as RealtimePostgresChangesPayload<BookingRow>)
      )
      .subscribe();

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [bookingId, rideId, passengerId]);

  return { lastEvent };
}
