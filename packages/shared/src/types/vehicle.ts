export type VehicleUpdateRequestStatus = "pending_review" | "approved" | "rejected";

export interface VehicleStructuralUpdate {
  plate_number?: string;
  make?: string;
  model?: string;
  year?: number;
}

export interface VehicleUpdateRequestRecord {
  id: string;
  plate_number: string | null;
  make: string | null;
  model: string | null;
  year: number | null;
  status: VehicleUpdateRequestStatus;
  submitted_at: string;
  rejection_reason: string | null;
}

export interface VehicleRegistration {
  plate_number: string;
  make: string;
  model: string;
  year: number;
  color: string;
  seat_count: number;
}

export interface VehicleUpdate {
  color?: string;
  seat_count?: number;
}

export interface Vehicle {
  id: string;
  plate_number: string;
  make: string;
  model: string;
  year: number;
  color: string;
  seat_count: number;
  registered_at: string;
}
