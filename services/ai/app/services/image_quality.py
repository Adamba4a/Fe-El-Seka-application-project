import cv2
import numpy as np

from app.models.verification import ImageQualityFlags

BLUR_SCORE_THRESHOLD = 100.0
GLARE_RATIO_THRESHOLD = 0.05


def blur_score(img_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def glare_ratio(img_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    overexposed = int(np.sum(gray >= 250))
    return overexposed / gray.size


def assess_quality(img_bgr: np.ndarray) -> ImageQualityFlags:
    blur = blur_score(img_bgr)
    glare = glare_ratio(img_bgr)
    return ImageQualityFlags(
        blur_score=blur,
        glare_ratio=glare,
        is_blurry=blur < BLUR_SCORE_THRESHOLD,
        is_glare=glare > GLARE_RATIO_THRESHOLD,
    )
