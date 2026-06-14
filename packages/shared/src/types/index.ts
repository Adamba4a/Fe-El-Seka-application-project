export type UserRole = "passenger" | "driver" | "both";
export type RideStatus = "active" | "paused" | "cancelled" | "completed";
export type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface User {
  id: string;
  phone: string;
  role: UserRole;
  createdAt: string;
}

export interface Ride {
  id: string;
  driverId: string;
  origin: GeoPoint;
  destination: GeoPoint;
  departureAt: string;
  status: RideStatus;
  createdAt: string;
}

export interface Booking {
  id: string;
  rideId: string;
  passengerId: string;
  status: BookingStatus;
  createdAt: string;
}
