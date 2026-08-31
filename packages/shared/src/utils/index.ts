export function formatPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.startsWith("20") && digits.length === 12) {
    return `+${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  }
  return phone;
}

export function formatDate(isoString: string, locale: "en" | "ar" = "en"): string {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    year: "numeric",
    month: "short",
    day: "numeric",
    numberingSystem: "latn",
  }).format(new Date(isoString));
}

export function formatCurrency(amount: number, locale: "en" | "ar" = "en"): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-EG" : "en-EG", {
    style: "currency",
    currency: "EGP",
    numberingSystem: "latn",
  }).format(amount);
}

// Mirrors services/api/app/services/commission_service.py's compute_per_seat_commission —
// keep these two in sync. Used for display only (e.g. the driver dashboard's net-earnings
// figure); the backend function above is the actual source of truth for money moved.
export const FARE_SPLIT_SEATS = 2;
export const COMMISSION_RATE = 0.2;

export function computeNetEarningsPerSeat(ride: {
  price_per_seat: string;
  fair_price_per_seat: string;
  fuel_cost_egp: number | null;
  distance_fee_egp: number | null;
  safety_margin_egp: number | null;
}): number {
  const pricePerSeat = parseFloat(ride.price_per_seat);
  const fairPricePerSeat = parseFloat(ride.fair_price_per_seat);
  const fuelCost = ride.fuel_cost_egp ?? 0;
  const safetyMargin = ride.safety_margin_egp ?? 0;

  // distance_fee is deliberately NOT subtracted here: it's saved toward the driver's
  // car-maintenance fund rather than lost, so it still counts as the driver's earnings.
  const markupCommissionPerSeat = Math.max(0, pricePerSeat - fairPricePerSeat) * COMMISSION_RATE;
  const perSeatCommission = (fuelCost * COMMISSION_RATE + safetyMargin) / FARE_SPLIT_SEATS + markupCommissionPerSeat;

  return pricePerSeat - perSeatCommission;
}
