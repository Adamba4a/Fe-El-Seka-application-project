export type SubmissionType = "passenger_id" | "driver_id_license";

export type SubmissionStatus = "pending_review" | "approved" | "rejected";

export interface VerificationSubmission {
  submission_id: string;
  status: SubmissionStatus;
  attempt_number: number;
}

export interface VerificationStatus {
  verification_status: string;
  attempt_number: number;
  is_locked: boolean;
  rejection_reason: string | null;
  lockout_message: string | null;
}

export interface AdminQueueItem {
  submission_id: string;
  user_id: string;
  user_name: string;
  email: string;
  submission_type: SubmissionType;
  submitted_at: string;
  attempt_number: number;
}

export interface AdminQueueResponse {
  total: number;
  page: number;
  items: AdminQueueItem[];
}

export interface AdminSubmissionDetail extends AdminQueueItem {
  document_signed_urls: {
    front_id: string;
    back_id: string;
    license?: string;
  };
}
