import cv2
import numpy as np
import pyarabic.araby as araby
import pytesseract
from pytesseract import Output
from rapidfuzz import fuzz

from app.services.document_crop import find_and_crop_document

TESSERACT_LANG = "ara+eng"


def _enhanced(img_bgr: np.ndarray) -> np.ndarray:
    """Standard remedy for blurry/low-res phone photos: upscale, denoise, and
    boost local contrast (CLAHE)."""
    upscaled = cv2.resize(img_bgr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def _thresholded(enhanced_gray: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(enhanced_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _ocr_confidence(variant: np.ndarray) -> float:
    data = pytesseract.image_to_data(variant, lang=TESSERACT_LANG, output_type=Output.DICT)
    return sum(
        float(conf) for conf, word in zip(data["conf"], data["text"]) if word.strip() and float(conf) >= 0
    )


def extract_text(img_bgr: np.ndarray) -> str:
    """Tries several preprocessing strengths and keeps whichever Tesseract is
    most confident about, rather than always forcing the same fixed pipeline.

    A single fixed upscale+denoise+CLAHE+Otsu-threshold pipeline was found to
    actively destroy text on sharp, high-res photos: on Egyptian ID cards the
    pyramid/sphinx watermark art is dark enough that global Otsu binarization
    merges it with the foreground text into unreadable black blobs, while raw
    grayscale (no processing at all) reads the same photo correctly. The
    right amount of preprocessing depends on the input photo's own quality,
    so all three variants are tried and scored instead of guessing one.
    """
    base = find_and_crop_document(img_bgr)
    if base is None:
        base = img_bgr

    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    enhanced = _enhanced(base)
    thresholded = _thresholded(enhanced)

    best_variant = max([gray, enhanced, thresholded], key=_ocr_confidence)
    return pytesseract.image_to_string(best_variant, lang=TESSERACT_LANG).strip()


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
