import cv2
import numpy as np
import pyarabic.araby as araby
import pytesseract
from rapidfuzz import fuzz

TESSERACT_LANG = "ara+eng"


def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    upscaled = cv2.resize(img_bgr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)
    _, thresholded = cv2.threshold(contrasted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresholded


def extract_text(img_bgr: np.ndarray) -> str:
    preprocessed = preprocess_for_ocr(img_bgr)
    return pytesseract.image_to_string(preprocessed, lang=TESSERACT_LANG).strip()


def name_match_score(display_name: str, ocr_text: str) -> float | None:
    """Fuzzy-matches the entered display name against the full OCR text blob.

    Deliberately does not try to isolate "the name line" -- field-level parsing
    proved unreliable on real phone photos during calibration, and this is an
    advisory-only signal for a human reviewer, not a gate.
    """
    if not display_name.strip() or not ocr_text.strip():
        return None
    normalized_name = araby.strip_tashkeel(display_name)
    normalized_text = araby.strip_tashkeel(ocr_text)
    return fuzz.partial_ratio(normalized_name, normalized_text) / 100.0
