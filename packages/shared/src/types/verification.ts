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
  pending_seconds?: number;
  is_aged?: boolean;
}

export interface AdminQueueResponse {
  total: number;
  page: number;
  items: AdminQueueItem[];
}

export interface AIImageQualityFlags {
  blur_score: number;
  glare_ratio: number;
  is_blurry: boolean;
  is_glare: boolean;
}

// Advisory-only hint surfaced next to the document viewer — never a decision.
// null means no AI read-out is available (AI was unreachable, or the
// submission predates this feature), not "AI checked and found nothing".
export interface AIReadout {
  name_match_score: number | null;
  ocr_text_front: string | null;
  ocr_text_back: string | null;
  face_match_score: number | null;
  id_face_detected: boolean | null;
  selfie_face_detected: boolean | null;
  image_quality: Record<string, AIImageQualityFlags> | null;
  reasons: string[] | null;
  model_version: string | null;
  processed_at: string | null;
}

export interface AdminSubmissionDetail extends AdminQueueItem {
  phone_number: string | null;
  profile_photo_signed_url: string | null;
  document_signed_urls: {
    front_id: string;
    back_id: string;
    license?: string;
  };
  ai_readout: AIReadout | null;
}
