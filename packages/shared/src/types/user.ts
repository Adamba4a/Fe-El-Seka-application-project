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
  created_at: string;
}

export interface ProfileSetup {
  role: "passenger" | "driver";
  display_name: string;
}

export interface ProfileUpdate {
  display_name?: string;
}
