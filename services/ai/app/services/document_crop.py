import cv2
import numpy as np


def _order_quad_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def find_and_crop_document(img_bgr: np.ndarray) -> np.ndarray | None:
    """Standard document-scanner approach: find the largest quadrilateral
    contour (the ID card edge against its background) and perspective-warp
    it flat. Raw phone photos routinely include background (table, hand) --
    measuring blur/glare or running OCR over that background rather than the
    card itself produces false positives (e.g. a bright white table reads as
    "significant glare" even when the card itself has none). Returns None if
    no confident card-like quad is found (caller should fall back to the full
    frame)."""
    h, w = img_bgr.shape[:2]
    frame_area = float(h * w)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_quad = None
    best_area = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 0.2 * frame_area:  # card should be a substantial chunk of frame
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and area > best_area:
            best_quad = approx.reshape(4, 2).astype(np.float32)
            best_area = area

    if best_quad is None:
        return None

    tl, tr, br, bl = _order_quad_points(best_quad)
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    if width < 100 or height < 60:
        return None

    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype=np.float32), dst)
    return cv2.warpPerspective(img_bgr, matrix, (width, height))
