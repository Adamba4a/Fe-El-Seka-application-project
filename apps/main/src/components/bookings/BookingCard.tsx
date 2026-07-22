"use client";

import { BookingStatusBadge } from "./BookingStatusBadge";

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
  onViewMap?: () => void;
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
      <div
        className="rounded-xl border border-border-default bg-surface-card cursor-pointer transition-shadow hover:shadow-md"
        onClick={onClick}
      >
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-sm text-content-primary">
              {booking.driver_display_name ?? "Driver"}
            </span>
            <BookingStatusBadge status={booking.status} />
          </div>
          <p className="text-xs text-content-muted">
            {formatDateTime(booking.departure_datetime)}
          </p>
          <div className="flex items-center justify-between text-sm">
            <span className="text-content-muted">Total</span>
            <span className="font-semibold text-content-primary">EGP {booking.total_price}</span>
          </div>
          {hasPremium && (
            <p className="text-xs text-amber-700">
              Premium service included
              {booking.premium_pickup_fee ? ` (+EGP ${booking.premium_pickup_fee} pickup)` : ""}
              {booking.premium_dropoff_fee ? ` (+EGP ${booking.premium_dropoff_fee} dropoff)` : ""}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Driver variant
  const { booking, onConfirm, onReject, onCancel, onViewMap, actionLoading, cancelAvailable = false } = props;
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
    <div className="rounded-xl border border-border-default bg-surface-card">
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-3">
          {booking.passenger.avatar_url ? (
            <img
              src={booking.passenger.avatar_url}
              alt={passengerName}
              className="h-10 w-10 rounded-full object-cover shrink-0"
            />
          ) : (
            <div className="h-10 w-10 rounded-full bg-surface-bg flex items-center justify-center shrink-0 text-sm font-semibold text-content-secondary">
              {initials}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm text-content-primary truncate">{passengerName}</p>
            <BookingStatusBadge status={booking.status} />
          </div>
          <div className="text-right text-sm shrink-0">
            <p className="font-semibold text-content-primary">EGP {booking.total_price}</p>
            <p className="text-xs text-content-muted">/ seat</p>
          </div>
        </div>

        {onViewMap ? (
          <button
            type="button"
            onClick={onViewMap}
            className="w-full flex items-center justify-between text-xs px-3 py-2 rounded-lg bg-surface-bg border border-transparent hover:border-border-default text-content-secondary transition-colors"
          >
            <span>View pickup &amp; dropoff on map</span>
            <span className="text-content-muted">→</span>
          </button>
        ) : (
          <div className="text-xs text-content-muted space-y-1">
            <p>
              <span className="font-medium text-content-primary">Boarding: </span>
              {formatCoord(booking.boarding_point)}
            </p>
            <p>
              <span className="font-medium text-content-primary">Alighting: </span>
              {formatCoord(booking.alighting_point)}
            </p>
          </div>
        )}

        {(booking.premium_pickup_requested || booking.premium_dropoff_requested) && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-2 text-xs text-amber-800 space-y-0.5">
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
            <button
              type="button"
              onClick={onConfirm}
              disabled={actionLoading}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-brand-primary hover:bg-brand-primary-hover text-content-inverse disabled:opacity-50 transition-colors"
            >
              Confirm
            </button>
            <button
              type="button"
              onClick={onReject}
              disabled={actionLoading}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-surface-destructive text-content-inverse disabled:opacity-50 transition-colors"
            >
              Reject
            </button>
          </div>
        )}

        {isConfirmed && cancelAvailable && (
          <button
            type="button"
            onClick={onCancel}
            disabled={actionLoading}
            className="w-full px-3 py-1.5 rounded-lg text-sm font-medium border border-border-default text-content-destructive hover:bg-status-cancelled-bg disabled:opacity-50 transition-colors"
          >
            Cancel Booking
          </button>
        )}
      </div>
    </div>
  );
}
