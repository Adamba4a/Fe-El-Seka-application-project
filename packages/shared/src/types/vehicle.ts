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
