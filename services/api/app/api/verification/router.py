from fastapi import APIRouter, Depends, File, UploadFile, status

from app.dependencies.auth import get_current_user
from app.models.verification import StatusResponse, SubmissionResponse
from app.services import verification_service

router = APIRouter()


@router.post("/submit", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_documents(
    front_id: UploadFile = File(...),
    back_id: UploadFile = File(...),
    license: UploadFile | None = File(None),
    profile: dict = Depends(get_current_user),
) -> dict:
    return await verification_service.submit_documents(
        user_id=profile["id"],
        user_role=profile["role"],
        front_id=front_id,
        back_id=back_id,
        license=license,
    )


@router.get("/status", response_model=StatusResponse)
def get_status(profile: dict = Depends(get_current_user)) -> dict:
    return verification_service.get_status(profile["id"])
