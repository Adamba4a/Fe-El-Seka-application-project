import { env } from "../env";

const base = env.apiUrl;

export interface PassengerBooking {
  booking_id: string;
  ride_id: string;
  status: "pending" | "confirmed" | "cancelled" | "completed";
  driver_display_name: string | null;
  departure_datetime: string | null;
  origin_address: string | null;
  destination_address: string | null;
  per_seat_price: string;
  total_price: string;
  created_at: string;
}

export interface PassengerBookingListResponse {
  bookings: PassengerBooking[];
  total: number;
  page: number;
  page_size: number;
}

export async function listBookings(
  token: string,
  params: { status?: string; page?: number; page_size?: number } = {}
): Promise<PassengerBookingListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));

  const res = await fetch(`${base}/api/v1/bookings/?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
