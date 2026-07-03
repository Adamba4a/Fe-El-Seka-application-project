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


class AdminQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminQueueItem]


class AdminSubmissionDetail(AdminQueueItem):
    document_signed_urls: dict


class RejectRequest(BaseModel):
    reason: str

    def model_post_init(self, __context) -> None:
        if not self.reason or not self.reason.strip():
            raise ValueError("Rejection reason is required")
