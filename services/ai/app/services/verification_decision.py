"""Assembles OCR/face/image-quality signals into a human-readable read-out.

Deliberately produces no decision (no auto_approve/auto_reject/needs_review).
Calibration against a real corpus (2026-07-25) showed both OCR and face-match
have too much genuine/impostor overlap to safely auto-decide -- every
submission still routes to the existing human admin queue. This module only
formats the raw signals as hints for that reviewer.
"""

from app.models.verification import FaceReadout, ImageQualityFlags, OCRReadout


def build_reasons(
    ocr: OCRReadout,
    face: FaceReadout | None,
    quality: dict[str, ImageQualityFlags],
) -> list[str]:
    reasons: list[str] = []

    if ocr.name_match_score is None:
        reasons.append("Could not extract readable text from the ID to compare against the entered name.")
    elif ocr.name_match_score >= 0.85:
        reasons.append(f"OCR-extracted text closely matches the entered name ({ocr.name_match_score:.0%}).")
    elif ocr.name_match_score < 0.5:
        reasons.append(f"OCR-extracted text has low similarity to the entered name ({ocr.name_match_score:.0%}).")
    else:
        reasons.append(f"OCR-extracted text partially matches the entered name ({ocr.name_match_score:.0%}).")

    if face is None:
        reasons.append("No selfie was provided, so face match could not be computed.")
    elif face.match_score is None:
        reasons.append("Face match could not be computed (face not detected in the ID photo and/or selfie).")
    else:
        reasons.append(f"Face similarity between ID photo and selfie: {face.match_score:.2f} (cosine).")

    for label, flags in quality.items():
        if flags.is_blurry:
            reasons.append(f"{label} image appears blurry.")
        if flags.is_glare:
            reasons.append(f"{label} image has significant glare.")

    return reasons
