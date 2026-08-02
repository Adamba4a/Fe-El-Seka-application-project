from pydantic import BaseModel


class SubmissionResponse(BaseModel):
    submission_id: str
    status: str
    attempt_number: int


class StatusResponse(BaseModel):
    verification_status: str
    attempt_number: int | None
    is_locked: bool
    rejection_reason: str | None
    lockout_message: str | None


class AdminQueueItem(BaseModel):
    submission_id: str
    user_id: str
    user_name: str
    email: str
    submission_type: str
    submitted_at: str
    attempt_number: int
    pending_seconds: int | None = None
    is_aged: bool | None = None


class AdminQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminQueueItem]


class AIReadout(BaseModel):
    name_match_score: float | None
    ocr_text_front: str | None
    ocr_text_back: str | None
    face_match_score: float | None
    id_face_detected: bool | None
    selfie_face_detected: bool | None
    image_quality: dict | None
    reasons: list[str] | None
    model_version: str | None
    processed_at: str | None


class AdminSubmissionDetail(AdminQueueItem):
    document_signed_urls: dict
    ai_readout: AIReadout | None = None


class RejectRequest(BaseModel):
    reason: str

    def model_post_init(self, __context) -> None:
        if not self.reason or not self.reason.strip():
            raise ValueError("Rejection reason is required")
