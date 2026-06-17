export type UserRole = "passenger" | "driver" | "both";
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

export interface Booking {
  id: string;
  rideId: string;
  passengerId: string;
  status: BookingStatus;
  createdAt: string;
}
