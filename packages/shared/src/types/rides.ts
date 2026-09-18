export type RideStatus = "scheduled" | "in_progress" | "completed" | "cancelled";
export type RideTripLeg = "one_way" | "outbound" | "return";
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
  fair_price_per_seat: string;
  fuel_cost_egp: number | null;
  distance_fee_egp: number | null;
  safety_margin_egp: number | null;
  status: RideStatus;
  cancellation_reason: string | null;
  cancellation_source: "driver" | "system" | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  route_geometry: object | null;
  group_id: string | null;
  group_name?: string | null;
  recurring_ride_definition_id: string | null;
  is_women_only: boolean;
  round_trip_group_id: string | null;
  trip_leg: RideTripLeg;
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
  final_price_per_seat?: number;
  group_id?: string;
  is_women_only?: boolean;
  journey_type?: "one_way" | "round_trip";
  return_departure_datetime?: string;
  return_total_seats?: number;
  return_final_price_per_seat?: number;
}

export interface EditRidePayload {
  destination?: Location;
  departure_datetime?: string;
  total_seats?: number;
  notes?: string;
  final_price_per_seat?: number;
  is_women_only?: boolean;
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

export type RecurringRideDefinitionStatus = "active" | "ended";

export interface RecurringRideDefinition {
  id: string;
  driver_id: string;
  vehicle_id: string;
  origin: Location;
  destination: Location;
  departure_time: string; // "HH:MM:SS"
  weekdays: number[]; // 0 = Sunday .. 6 = Saturday
  total_seats: number;
  price_per_seat: string;
  notes: string | null;
  status: RecurringRideDefinitionStatus;
  created_at: string;
  updated_at: string;
  upcoming_instance_count?: number | null;
  journey_type: "one_way" | "round_trip";
  is_women_only: boolean;
  return_departure_time: string | null;
  return_total_seats: number | null;
  return_price_per_seat: string | null;
}

export interface CreateRecurringRideDefinitionPayload {
  vehicle_id: string;
  origin: Location;
  destination: Location;
  departure_time: string; // "HH:MM"
  weekdays: number[];
  total_seats: number;
  price_per_seat: number;
  notes?: string;
  journey_type?: "one_way" | "round_trip";
  is_women_only?: boolean;
  return_departure_time?: string;
  return_total_seats?: number;
  return_price_per_seat?: number;
}

export interface EditRecurringRideDefinitionPayload {
  origin?: Location;
  destination?: Location;
  departure_time?: string;
  weekdays?: number[];
  total_seats?: number;
  price_per_seat?: number;
  notes?: string;
  journey_type?: "one_way" | "round_trip";
  is_women_only?: boolean;
  return_departure_time?: string;
  return_total_seats?: number;
  return_price_per_seat?: number;
}

export interface RecurringOccurrenceOverridePayload {
  outbound_departure_datetime: string;
  return_departure_datetime: string;
}

export interface RecurringRideDefinitionListResponse {
  definitions: RecurringRideDefinition[];
}

export interface RecurringRideDefinitionDetailResponse {
  definition: RecurringRideDefinition;
  instances: Ride[];
  missing_weekly_occurrences: number;
}

export interface RecurringRideDefinitionUpdateResponse {
  definition: RecurringRideDefinition;
  updated_instance_count: number;
}
