"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { BookingStatusBadge } from "./BookingStatusBadge";
import { RatingBadge } from "@/components/ui/RatingBadge";
import { formatCurrency } from "@fe-el-seka/shared";
import type { Locale } from "@fe-el-seka/shared";

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
  passenger: {
    display_name?: string;
    avatar_url?: string;
    rating_avg?: number | null;
    rating_count?: number;
  };
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
  /** Links to the passenger's public profile; the backend only exposes their phone number there once the booking is confirmed/completed */
  viewProfileHref?: string;
}

type BookingCardProps = PassengerVariantProps | DriverVariantProps;

function formatDateTime(iso: string | undefined, locale: Locale) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(new Date(iso));
}

function formatCoord(pt: { lat: number; lng: number }) {
  return `${pt.lat.toFixed(4)}, ${pt.lng.toFixed(4)}`;
}

export function BookingCard(props: BookingCardProps) {
  const t = useTranslations("bookingCard");
  const locale = useLocale() as Locale;
  if (props.variant === "passenger") {
    const { booking, onClick } = props;
    const hasPremium = booking.premium_pickup_requested || booking.premium_dropoff_requested;

    return (
      <div
        className="rounded-2xl bg-dash-surface shadow-sm cursor-pointer transition-shadow hover:shadow-md"
        onClick={onClick}
      >
        <div className="p-5 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <span className="font-bold text-lg leading-tight text-dash-navy">
              {booking.driver_display_name ?? t("defaultDriverName")}
            </span>
            <BookingStatusBadge status={booking.status} />
          </div>
          <p className="text-sm text-dash-text-muted">
            {formatDateTime(booking.departure_datetime, locale)}
          </p>
          <div className="h-px bg-dash-border" />
          <div className="flex items-center justify-between text-sm">
            <span className="text-dash-text-muted">{t("total")}</span>
            <span className="text-xl font-bold text-dash-navy">{formatCurrency(Number(booking.total_price), locale)}</span>
          </div>
          {hasPremium && (
            <p className="text-xs text-amber-700">
              {t("premiumServiceIncluded")}
              {booking.premium_pickup_fee ? t("pickupFeeNote", { fee: booking.premium_pickup_fee }) : ""}
              {booking.premium_dropoff_fee ? t("dropoffFeeNote", { fee: booking.premium_dropoff_fee }) : ""}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Driver variant
  const { booking, onConfirm, onReject, onCancel, onViewMap, actionLoading, cancelAvailable = false, viewProfileHref } = props;
  const isPending = booking.status === "pending";
  const isConfirmed = booking.status === "confirmed";
  const passengerName = booking.passenger.display_name ?? t("defaultPassengerName");
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
            <div className="flex items-center gap-2">
              <BookingStatusBadge status={booking.status} />
              <RatingBadge
                ratingAvg={booking.passenger.rating_avg ?? null}
                ratingCount={booking.passenger.rating_count ?? 0}
              />
            </div>
          </div>
          <div className="text-end text-sm shrink-0">
            <p className="font-semibold text-content-primary">{formatCurrency(Number(booking.total_price), locale)}</p>
            <p className="text-xs text-content-muted">{t("perSeat")}</p>
          </div>
        </div>

        {onViewMap ? (
          <button
            type="button"
            onClick={onViewMap}
            className="w-full flex items-center justify-between text-xs px-3 py-2 rounded-lg bg-surface-bg border border-transparent hover:border-border-default text-content-secondary transition-colors"
          >
            <span>{t("viewPickupDropoffMap")}</span>
            <span className="text-content-muted">→</span>
          </button>
        ) : (
          <div className="text-xs text-content-muted space-y-1">
            <p>
              <span className="font-medium text-content-primary">{t("boardingLabel")} </span>
              {formatCoord(booking.boarding_point)}
            </p>
            <p>
              <span className="font-medium text-content-primary">{t("alightingLabel")} </span>
              {formatCoord(booking.alighting_point)}
            </p>
          </div>
        )}

        {(booking.premium_pickup_requested || booking.premium_dropoff_requested) && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-2 text-xs text-amber-800 space-y-0.5">
            <p className="font-medium">{t("premiumRequest")}</p>
            {booking.premium_pickup_requested && (
              <p>{t("pickupDetour", { fee: booking.premium_pickup_fee ?? "—" })}</p>
            )}
            {booking.premium_dropoff_requested && (
              <p>{t("dropoffDetour", { fee: booking.premium_dropoff_fee ?? "—" })}</p>
            )}
          </div>
        )}

        {viewProfileHref && (
          <Link
            href={viewProfileHref}
            className="inline-block text-xs text-brand-primary hover:underline"
          >
            {t("viewProfile")}
          </Link>
        )}

        {isPending && (
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onConfirm}
              disabled={actionLoading}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-dash-primary hover:opacity-90 text-content-inverse disabled:opacity-50 transition-opacity"
            >
              {t("confirm")}
            </button>
            <button
              type="button"
              onClick={onReject}
              disabled={actionLoading}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-surface-destructive text-content-inverse disabled:opacity-50 transition-colors"
            >
              {t("reject")}
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
            {t("cancelBooking")}
          </button>
        )}
      </div>
    </div>
  );
}
