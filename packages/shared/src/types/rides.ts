export type RideStatus = "scheduled" | "in_progress" | "completed" | "cancelled";
export type RideAction = "created" | "edited" | "cancelled" | "started" | "completed";

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface Location {
  coordinates: Coordinates;
  address: string;
}

export interface Ride {
  id: string;
  driver_id: string;
  vehicle_id: string;
  origin: Location;
  destination: Location;
  departure_datetime: string;
  total_seats: number;
  booked_seats: number;
  available_seats: number;
  price_per_seat: string;
  status: RideStatus;
  cancellation_reason: string | null;
  cancellation_source: "driver" | "system" | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  route_geometry: object | null;
}

export interface RideHistoryEntry {
  id: string;
  actor_id: string | null;
  action: RideAction;
  changed_fields: Record<string, { before: unknown; after: unknown }> | null;
  reason: string | null;
  created_at: string;
}

export interface CreateRidePayload {
  origin: Location;
  destination: Location;
  departure_datetime: string;
  total_seats: number;
  notes?: string;
}

export interface EditRidePayload {
  destination?: Location;
  departure_datetime?: string;
  total_seats?: number;
  notes?: string;
}

export interface CancelRidePayload {
  reason: string;
}

export interface RideListResponse {
  rides: Ride[];
  total: number;
  page: number;
  page_size: number;
}

export interface RideDetailResponse {
  ride: Ride;
  history: RideHistoryEntry[];
}
