from datetime import datetime

from pydantic import BaseModel


class ImageQualityFlags(BaseModel):
    blur_score: float
    glare_ratio: float
    is_blurry: bool
    is_glare: bool


class OCRReadout(BaseModel):
    extracted_text_front: str
    extracted_text_back: str
    name_match_score: float | None = None


class FaceReadout(BaseModel):
    match_score: float | None = None
    id_face_detected: bool
    selfie_face_detected: bool


class VerificationReadout(BaseModel):
    ocr: OCRReadout
    face: FaceReadout | None = None
    image_quality: dict[str, ImageQualityFlags]
    reasons: list[str]
    model_version: str
    processed_at: datetime
