import logging
from datetime import UTC, datetime

import cv2
import numpy as np
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from app.config import get_settings
from app.models.verification import FaceReadout, OCRReadout, VerificationReadout
from app.services import face_service, image_quality, ocr_service, verification_decision

router = APIRouter(tags=["verification"])
logger = logging.getLogger(__name__)


async def _decode_image(file: UploadFile, field_name: str) -> np.ndarray:
    data = await file.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=422, detail=f"Could not decode image for '{field_name}'.")
    return img


@router.post("/identity", response_model=VerificationReadout)
async def verify_identity(
    request: Request,
    front_id: UploadFile,
    back_id: UploadFile,
    display_name: str = Form(...),
    submission_type: str = Form(...),
    selfie: UploadFile | None = None,
) -> VerificationReadout:
    face_models: dict | None = getattr(request.app.state, "face_models", None)
    if face_models is None:
        raise HTTPException(status_code=503, detail="Face-match models are not available.")
    detector = face_models["detector"]
    recognizer = face_models["recognizer"]

    front_img = await _decode_image(front_id, "front_id")
    back_img = await _decode_image(back_id, "back_id")
    selfie_img = await _decode_image(selfie, "selfie") if selfie is not None else None

    front_text = ocr_service.extract_text(front_img)
    back_text = ocr_service.extract_text(back_img)
    combined_text = f"{front_text}\n{back_text}"
    name_score = ocr_service.name_match_score(display_name, combined_text)
    ocr_readout = OCRReadout(
        extracted_text_front=front_text,
        extracted_text_back=back_text,
        name_match_score=name_score,
    )

    face_readout: FaceReadout | None = None
    if selfie_img is not None:
        score, id_detected, selfie_detected = face_service.face_match(
            front_img, selfie_img, detector, recognizer
        )
        face_readout = FaceReadout(
            match_score=score,
            id_face_detected=id_detected,
            selfie_face_detected=selfie_detected,
        )

    quality = {
        "front_id": image_quality.assess_quality(front_img),
        "back_id": image_quality.assess_quality(back_img),
    }
    if selfie_img is not None:
        quality["selfie"] = image_quality.assess_quality(selfie_img)

    reasons = verification_decision.build_reasons(ocr_readout, face_readout, quality)

    settings = get_settings()
    logger.info(
        "endpoint=verify_identity submission_type=%s name_match=%s face_match=%s",
        submission_type, name_score, face_readout.match_score if face_readout else None,
    )

    return VerificationReadout(
        ocr=ocr_readout,
        face=face_readout,
        image_quality=quality,
        reasons=reasons,
        model_version=settings.ai_version,
        processed_at=datetime.now(UTC),
    )
