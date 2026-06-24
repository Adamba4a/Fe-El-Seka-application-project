"use client";

import { BookingStatusBadge } from "./BookingStatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface PassengerBooking {
  booking_id: string;
  ride_id: string;
  status: BookingStatus;
  driver_display_name?: string;
  departure_datetime?: string;
  per_seat_price: string;
  total_price: string;
  premium_pickup_requested?: boolean;
  premium_dropoff_requested?: boolean;
  premium_pickup_fee?: string | null;
  premium_dropoff_fee?: string | null;
}

interface DriverBooking {
  booking_id: string;
  status: BookingStatus;
  passenger: { display_name?: string; avatar_url?: string };
  per_seat_price: string;
  total_price: string;
  boarding_point: { lat: number; lng: number };
  alighting_point: { lat: number; lng: number };
  premium_pickup_requested?: boolean;
  premium_pickup_fee?: string | null;
  premium_dropoff_requested?: boolean;
  premium_dropoff_fee?: string | null;
}

interface PassengerVariantProps {
  variant: "passenger";
  booking: PassengerBooking;
  onClick?: () => void;
}

interface DriverVariantProps {
  variant: "driver";
  booking: DriverBooking;
  onConfirm?: () => void;
  onReject?: () => void;
  onCancel?: () => void;
  actionLoading?: boolean;
  /** Set false to hide cancel until Phase 7 endpoint is live */
  cancelAvailable?: boolean;
}

type BookingCardProps = PassengerVariantProps | DriverVariantProps;

function formatDateTime(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCoord(pt: { lat: number; lng: number }) {
  return `${pt.lat.toFixed(4)}, ${pt.lng.toFixed(4)}`;
}

export function BookingCard(props: BookingCardProps) {
  if (props.variant === "passenger") {
    const { booking, onClick } = props;
    const hasPremium = booking.premium_pickup_requested || booking.premium_dropoff_requested;

    return (
      <Card
        className="cursor-pointer transition-shadow hover:shadow-md"
        onClick={onClick}
      >
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-sm">
              {booking.driver_display_name ?? "Driver"}
            </span>
            <BookingStatusBadge status={booking.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(booking.departure_datetime)}
          </p>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Total</span>
            <span className="font-semibold">EGP {booking.total_price}</span>
          </div>
          {hasPremium && (
            <p className="text-xs text-amber-700">
              Premium service included
              {booking.premium_pickup_fee ? ` (+EGP ${booking.premium_pickup_fee} pickup)` : ""}
              {booking.premium_dropoff_fee ? ` (+EGP ${booking.premium_dropoff_fee} dropoff)` : ""}
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  // Driver variant
  const { booking, onConfirm, onReject, onCancel, actionLoading, cancelAvailable = false } = props;
  const isPending = booking.status === "pending";
  const isConfirmed = booking.status === "confirmed";
  const passengerName = booking.passenger.display_name ?? "Passenger";
  const initials = passengerName
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-3">
          <Avatar className="h-10 w-10">
            <AvatarImage src={booking.passenger.avatar_url ?? ""} alt={passengerName} />
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">{passengerName}</p>
            <BookingStatusBadge status={booking.status} />
          </div>
          <div className="text-right text-sm">
            <p className="font-semibold">EGP {booking.total_price}</p>
            <p className="text-xs text-muted-foreground">/ seat</p>
          </div>
        </div>

        <div className="text-xs text-muted-foreground space-y-1">
          <p>
            <span className="font-medium text-foreground">Boarding: </span>
            {formatCoord(booking.boarding_point)}
          </p>
          <p>
            <span className="font-medium text-foreground">Alighting: </span>
            {formatCoord(booking.alighting_point)}
          </p>
        </div>

        {(booking.premium_pickup_requested || booking.premium_dropoff_requested) && (
          <div className="rounded-md bg-amber-50 border border-amber-200 p-2 text-xs text-amber-800 space-y-0.5">
            <p className="font-medium">Premium Request</p>
            {booking.premium_pickup_requested && (
              <p>Pickup detour: +EGP {booking.premium_pickup_fee ?? "—"}</p>
            )}
            {booking.premium_dropoff_requested && (
              <p>Dropoff detour: +EGP {booking.premium_dropoff_fee ?? "—"}</p>
            )}
          </div>
        )}

        {isPending && (
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              className="flex-1"
              onClick={onConfirm}
              disabled={actionLoading}
            >
              Confirm
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="flex-1"
              onClick={onReject}
              disabled={actionLoading}
            >
              Reject
            </Button>
          </div>
        )}

        {isConfirmed && cancelAvailable && (
          <Button
            size="sm"
            variant="outline"
            className="w-full border-red-200 text-red-600 hover:bg-red-50"
            onClick={onCancel}
            disabled={actionLoading}
          >
            Cancel Booking
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
