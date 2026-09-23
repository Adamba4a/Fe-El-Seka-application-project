const base = process.env.NEXT_PUBLIC_API_URL!;

export type RideStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

export interface RideListItem {
  ride_id: string;
  status: RideStatus;
  departure_datetime: string;
  origin_address: string;
  destination_address: string;
  total_seats: number;
  booked_seats: number;
  available_seats: number;
  price_per_seat: string;
  net_commission_egp: string;
  created_at: string;
  driver_id: string;
  driver_display_name: string;
  is_featured: boolean;
  featured_at: string | null;
  featured_by_display_name: string | null;
  recurring_ride_definition_id: string | null;
  round_trip_group_id: string | null;
  trip_leg: "one_way" | "outbound" | "return" | null;
}

export interface RideListResponse {
  total: number;
  page: number;
  limit: number;
  items: RideListItem[];
}

export interface RideListParams {
  status?: RideStatus;
  q?: string;
  date?: string;
  page?: number;
}

export interface RideDetail {
  ride_id: string;
  status: RideStatus;
  departure_datetime: string;
  origin_address: string;
  destination_address: string;
  total_seats: number;
  booked_seats: number;
  available_seats: number;
  price_per_seat: string;
  net_commission_egp: string;
  notes: string | null;
  cancellation_reason: string | null;
  cancellation_source: string | null;
  created_at: string;
  updated_at: string;
  is_featured: boolean;
  featured_at: string | null;
  featured_by_display_name: string | null;
  driver: {
    driver_id: string;
    display_name: string;
    email: string;
    rating_avg: number | null;
    rating_count: number;
  };
  vehicle: {
    plate_number: string;
    make: string;
    model: string;
    color: string;
  };
}

export interface RideBooking {
  booking_id: string;
  status: string;
  seats: number;
  total_price: string;
  created_at: string;
  passenger_id: string;
  passenger_display_name: string;
}

export interface RideDetailResponse {
  ride: RideDetail;
  bookings: RideBooking[];
}

export interface RecurringSeriesOccurrence {
  ride_id: string;
  status: RideStatus;
  departure_datetime: string;
  trip_leg: "one_way" | "outbound" | "return" | null;
  origin_address: string;
  destination_address: string;
  total_seats: number;
  booked_seats: number;
  available_seats: number;
  price_per_seat: string;
  bookings: RideBooking[];
}

export interface RecurringSeriesResponse {
  definition_id: string;
  driver: { driver_id: string; display_name: string };
  occurrences: RecurringSeriesOccurrence[];
}

export async function list(token: string, params: RideListParams = {}): Promise<RideListResponse> {
  const search = new URLSearchParams({ page: String(params.page ?? 1), limit: "20" });
  if (params.status) search.set("status", params.status);
  if (params.q) search.set("q", params.q);
  if (params.date) search.set("date", params.date);
  const res = await fetch(`${base}/api/admin/rides/?${search}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getDetail(token: string, rideId: string): Promise<RideDetailResponse> {
  const res = await fetch(`${base}/api/admin/rides/${rideId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getRecurringSeries(token: string, definitionId: string): Promise<RecurringSeriesResponse> {
  const res = await fetch(`${base}/api/admin/rides/series/${definitionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // The admin application is deliberately local-only and can be updated ahead
  // of its production API.  Keep the series screen usable during that rollout
  // by composing the already-deployed list/detail endpoints if the dedicated
  // series endpoint is not present yet.
  if (res.status === 404) return getRecurringSeriesFromLegacyEndpoints(token, definitionId);
  if (!res.ok) throw await res.json();
  return res.json();
}

async function getRecurringSeriesFromLegacyEndpoints(
  token: string,
  definitionId: string
): Promise<RecurringSeriesResponse> {
  const headers = { Authorization: `Bearer ${token}` };
  const firstResponse = await fetch(`${base}/api/admin/rides/?page=1&limit=100`, { headers });
  if (!firstResponse.ok) throw await firstResponse.json();

  const firstPage = await firstResponse.json() as RideListResponse;
  const pages = Math.ceil(firstPage.total / firstPage.limit);
  const pageResults = await Promise.all(
    Array.from({ length: Math.max(0, pages - 1) }, (_, index) =>
      fetch(`${base}/api/admin/rides/?page=${index + 2}&limit=100`, { headers })
        .then(async (response) => {
          if (!response.ok) throw await response.json();
          return response.json() as Promise<RideListResponse>;
        })
    )
  );
  const seriesRides = [firstPage, ...pageResults]
    .flatMap((page) => page.items)
    .filter((ride) => ride.recurring_ride_definition_id === definitionId)
    .sort((a, b) => b.departure_datetime.localeCompare(a.departure_datetime));

  if (seriesRides.length === 0) {
    throw { message: "Recurring series not found" };
  }

  const details = await Promise.all(seriesRides.map((ride) => getDetail(token, ride.ride_id)));
  return {
    definition_id: definitionId,
    driver: {
      driver_id: seriesRides[0].driver_id,
      display_name: seriesRides[0].driver_display_name,
    },
    occurrences: seriesRides.map((ride, index) => ({
      ride_id: ride.ride_id,
      status: ride.status,
      departure_datetime: ride.departure_datetime,
      trip_leg: ride.trip_leg,
      origin_address: ride.origin_address,
      destination_address: ride.destination_address,
      total_seats: ride.total_seats,
      booked_seats: ride.booked_seats,
      available_seats: ride.available_seats,
      price_per_seat: ride.price_per_seat,
      bookings: details[index].bookings,
    })),
  };
}

export interface FeaturedToggleResponse {
  ride_id: string;
  is_featured: boolean;
  featured_at: string;
  featured_by: string;
}

export async function featureRide(token: string, rideId: string): Promise<FeaturedToggleResponse> {
  const res = await fetch(`${base}/api/admin/rides/${rideId}/feature`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function unfeatureRide(token: string, rideId: string): Promise<FeaturedToggleResponse> {
  const res = await fetch(`${base}/api/admin/rides/${rideId}/unfeature`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
