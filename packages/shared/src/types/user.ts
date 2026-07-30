export type Role = "passenger" | "driver" | "admin";

export type VerificationStatus =
  | "unverified"
  | "pending_review"
  | "verified"
  | "rejected"
  | "suspended";

export interface Profile {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  profile_photo_url: string | null;
  verification_status: VerificationStatus;
  is_submission_locked: boolean;
  rating_avg: number | null;
  rating_count: number;
  created_at: string;
}

export interface PublicRideSummary {
  origin_address: string | null;
  destination_address: string | null;
  departure_datetime: string | null;
}

export interface PublicProfile {
  id: string;
  display_name: string;
  role: Role;
  profile_photo_url: string | null;
  verification_status: VerificationStatus;
  rating_avg: number | null;
  rating_count: number;
  total_rides: number;
  recent_rides: PublicRideSummary[];
}

export interface ProfileSetup {
  role: "passenger" | "driver";
  display_name: string;
}

export interface ProfileUpdate {
  display_name?: string;
}
