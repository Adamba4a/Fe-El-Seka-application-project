"""
Standalone OCR + face-match + image-quality accuracy validation against a real,
consented calibration corpus (see feedback_verification_data_privacy: no
scraped/synthetic ID data -- real camera/lighting artifacts matter for threshold
accuracy).

Run inside the calibration Docker image (scripts/Dockerfile.calibration) so
Tesseract's behavior matches the actual Linux deployment target, not a local
Windows install:

    cd services/ai
    docker build -f scripts/Dockerfile.calibration -t fe-el-seka-ai-calibration .
    docker run --rm -v "<calibration-data-dir>:/data:ro" fe-el-seka-ai-calibration --data-dir /data

This script never writes anything back to the data directory or the repo -- it
only prints aggregate metrics to stdout. It requires no ground-truth labels
(names, ID numbers): face-match genuine/impostor grouping comes from folder
names alone, and OCR is scored via cross-variant self-consistency, not a
hardcoded transcript.

Expected --data-dir layout: numbered person folders ("1", "2", ...), optionally
with "<n>_blured" / "<n>_light_reflection" quality-variant siblings. All images
in folders sharing the same base number are treated as one identity.
"""

from __future__ import annotations

import argparse
import itertools
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_VARIANT_SUFFIX_RE = re.compile(r"^(?P<base>.+?)_(blured|light_reflection)$")

_DET_MODEL = "face_detection_yunet_2023mar.onnx"
_REC_MODEL = "face_recognition_sface_2021dec.onnx"
_ARCFACE_MODEL = "arcfaceresnet100-8.onnx"


@dataclass
class ImageRecord:
    identity: str
    variant: str  # "base", "blured", "light_reflection"
    path: Path
    face_embedding: np.ndarray | None = None  # SFace
    face_embedding_arcface: np.ndarray | None = None
    ocr_text_raw: str = ""
    ocr_text_pre: str = ""
    ocr_text_paddle: str = ""
    doc_crop_used: bool = False
    blur_score: float = 0.0
    glare_ratio: float = 0.0


def discover_images(data_dir: Path) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    for folder in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        m = _VARIANT_SUFFIX_RE.match(folder.name)
        identity, variant = (m.group("base"), "blured" if "blured" in folder.name else "light_reflection") if m else (folder.name, "base")
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() in _IMAGE_EXTS:
                records.append(ImageRecord(identity=identity, variant=variant, path=f))
    return records


def load_face_models(weights_dir: Path) -> tuple[cv2.FaceDetectorYN, cv2.FaceRecognizerSF]:
    detector = cv2.FaceDetectorYN.create(
        str(weights_dir / _DET_MODEL), "", (320, 320), score_threshold=0.7
    )
    recognizer = cv2.FaceRecognizerSF.create(str(weights_dir / _REC_MODEL), "")
    return detector, recognizer


def detect_faces(img_bgr: np.ndarray, detector: cv2.FaceDetectorYN) -> np.ndarray | None:
    h, w = img_bgr.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img_bgr)
    return faces


def detect_and_align_face(
    img_bgr: np.ndarray,
    detector: cv2.FaceDetectorYN,
    recognizer: cv2.FaceRecognizerSF,
    score_threshold: float,
) -> np.ndarray | None:
    """Detect the largest face and return SFace's canonical 112x112 aligned
    crop. Both SFace and ArcFace embeddings are computed from this same crop
    so the two models are compared on identical input, not confounded by
    different detection/alignment code paths."""
    detector.setScoreThreshold(score_threshold)
    faces = detect_faces(img_bgr, detector)
    if faces is None or len(faces) == 0:
        return None
    # faces: Nx15 [x, y, w, h, landmarks..., score] -- pick largest box area
    largest = max(faces, key=lambda f: f[2] * f[3])
    return recognizer.alignCrop(img_bgr, largest)


def sface_embedding(aligned_bgr: np.ndarray, recognizer: cv2.FaceRecognizerSF) -> np.ndarray:
    # SFace requires a fixed 112x112 input, so we can't just upscale the crop --
    # instead apply an unsharp mask to counter the softness of a printed,
    # re-photographed ID photo (vs. a crisp phone-camera selfie), on the
    # chance that softness rather than genuine identity difference is driving
    # the genuine/impostor overlap.
    blurred = cv2.GaussianBlur(aligned_bgr, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(aligned_bgr, 1.5, blurred, -0.5, 0)
    return recognizer.feature(sharpened)


def load_arcface_session(weights_dir: Path):
    import onnxruntime as ort

    return ort.InferenceSession(
        str(weights_dir / _ARCFACE_MODEL), providers=["CPUExecutionProvider"]
    )


def arcface_embedding(aligned_bgr: np.ndarray, session) -> np.ndarray:
    """Preprocessing per the onnx/models arcfaceresnet100-8 reference sample:
    RGB, raw [0, 255] float32, NCHW -- no mean/scale normalization (the graph
    handles that internally). An earlier [-1, 1]-normalized attempt produced
    near-identical genuine/impostor cosine similarities (~0.97 for everyone),
    a classic symptom of a preprocessing mismatch collapsing embeddings
    toward a shared direction rather than a real accuracy result."""
    img = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    img = np.transpose(img, (2, 0, 1))[None, ...]
    input_name = session.get_inputs()[0].name
    out = session.run(None, {input_name: img})[0]
    return out.flatten()


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
    it flat. Raw phone photos include background and camera-angle skew that
    plain contrast/denoise preprocessing can't fix -- Tesseract expects a
    frame-filling, non-skewed document. Returns None if no confident
    card-like quad is found (caller should fall back to the full frame)."""
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


def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """Standard remedy for phone photos of physical documents: upscale, denoise,
    boost local contrast (CLAHE), then binarize. Cheap to try before concluding
    Tesseract itself is unusable on this corpus."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    scale = 2.0
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def blur_and_glare(img_bgr: np.ndarray) -> tuple[float, float]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    glare_ratio = float(np.mean(gray >= 250))
    return float(blur_score), glare_ratio


def run_ocr(img_bgr: np.ndarray, preprocess: bool) -> str:
    img = preprocess_for_ocr(img_bgr) if preprocess else cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(img, lang="ara").strip()


def load_paddleocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(lang="ar", use_textline_orientation=True)


def run_paddleocr(img_bgr: np.ndarray, ocr_engine) -> str:
    """PaddleOCR ships its own trained text-detection stage, so unlike
    Tesseract it doesn't need a pre-cropped, frame-filling document -- run it
    on the raw, uncropped photo and let it find the text regions itself.
    Tries the newer predict() pipeline API first, falls back to the legacy
    ocr() API, since the installed version isn't pinned and the interface
    has changed across recent PaddleOCR releases."""
    try:
        pages = ocr_engine.predict(img_bgr)
        texts: list[str] = []
        for page in pages:
            rec_texts = page.get("rec_texts") if hasattr(page, "get") else getattr(page, "rec_texts", None)
            if rec_texts:
                texts.extend(rec_texts)
        return " | ".join(texts)
    except AttributeError:
        pass
    result = ocr_engine.ocr(img_bgr, cls=True)
    if not result or not result[0]:
        return ""
    return " | ".join(line[1][0] for line in result[0])


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.flatten(), b.flatten()
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def summarize(label: str, values: list[float]) -> None:
    if not values:
        print(f"  {label}: (no data)")
        return
    print(
        f"  {label}: n={len(values)} min={min(values):.3f} "
        f"median={statistics.median(values):.3f} max={max(values):.3f} "
        f"mean={statistics.mean(values):.3f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument(
        "--weights-dir",
        type=Path,
        default=Path(__file__).parent.parent / "app" / "models" / "weights",
    )
    parser.add_argument(
        "--face-score-threshold",
        type=float,
        default=0.5,
        help="YuNet detection score threshold (default lowered from the 0.7 "
        "OpenCV default -- first run at 0.7 only found faces in 47%% of images).",
    )
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"ERROR: --data-dir {args.data_dir} is not a directory", file=sys.stderr)
        return 1

    records = discover_images(args.data_dir)
    if not records:
        print(f"ERROR: no images found under {args.data_dir}", file=sys.stderr)
        return 1

    identities = sorted({r.identity for r in records})
    print(f"Discovered {len(records)} images across {len(identities)} identities: {identities}\n")

    detector, recognizer = load_face_models(args.weights_dir)

    arcface_session = None
    try:
        arcface_session = load_arcface_session(args.weights_dir)
    except Exception as exc:  # noqa: BLE001 - experimental model, degrade gracefully
        print(f"WARN: ArcFace unavailable, skipping ({exc})\n", file=sys.stderr)

    paddle_engine = None
    try:
        paddle_engine = load_paddleocr()
    except Exception as exc:  # noqa: BLE001 - experimental model, degrade gracefully
        print(f"WARN: PaddleOCR unavailable, skipping ({exc})\n", file=sys.stderr)

    faces_found = 0
    for r in records:
        img = cv2.imread(str(r.path))
        if img is None:
            print(f"  WARN: failed to read {r.path.name}", file=sys.stderr)
            continue
        r.blur_score, r.glare_ratio = blur_and_glare(img)

        aligned = detect_and_align_face(img, detector, recognizer, args.face_score_threshold)
        if aligned is not None:
            faces_found += 1
            r.face_embedding = sface_embedding(aligned, recognizer)
            if arcface_session is not None:
                r.face_embedding_arcface = arcface_embedding(aligned, arcface_session)

        doc_img = find_and_crop_document(img)
        ocr_input = doc_img if doc_img is not None else img
        r.doc_crop_used = doc_img is not None
        r.ocr_text_raw = run_ocr(ocr_input, preprocess=False)
        r.ocr_text_pre = run_ocr(ocr_input, preprocess=True)
        if paddle_engine is not None:
            try:
                r.ocr_text_paddle = run_paddleocr(img, paddle_engine)
            except Exception as exc:  # noqa: BLE001 - keep the run alive per-image
                print(f"  WARN: PaddleOCR failed on {r.path.name} ({exc})", file=sys.stderr)

    print(f"Face detected in {faces_found}/{len(records)} images "
          f"(score_threshold={args.face_score_threshold})\n")

    raw_nonempty = sum(1 for r in records if r.ocr_text_raw)
    pre_nonempty = sum(1 for r in records if r.ocr_text_pre)
    paddle_nonempty = sum(1 for r in records if r.ocr_text_paddle)
    doc_crops = sum(1 for r in records if r.doc_crop_used)
    print(f"OCR non-empty: tesseract-raw={raw_nonempty}/{len(records)} "
          f"tesseract-preprocessed={pre_nonempty}/{len(records)} "
          f"paddleocr={paddle_nonempty}/{len(records)}")
    print(f"Document quad detected & perspective-cropped (Tesseract path only): "
          f"{doc_crops}/{len(records)} (remainder ran Tesseract on the full frame -- "
          f"expected for selfies, which have no card to crop and correctly yield "
          f"empty OCR; PaddleOCR always runs on the full frame, it detects text "
          f"regions itself)\n")

    # --- Face-match genuine vs impostor separation (SFace vs ArcFace) ---
    for label, attr in (("SFace", "face_embedding"), ("ArcFace", "face_embedding_arcface")):
        print(f"=== Face-match similarity [{label}] (genuine = same identity, impostor = different) ===")
        with_faces = [r for r in records if getattr(r, attr) is not None]
        if not with_faces:
            print("  (no embeddings -- model unavailable this run)\n")
            continue
        genuine, impostor = [], []
        for a, b in itertools.combinations(with_faces, 2):
            sim = cosine_sim(getattr(a, attr), getattr(b, attr))
            (genuine if a.identity == b.identity else impostor).append(sim)
        summarize("genuine pairs", genuine)
        summarize("impostor pairs", impostor)
        if genuine and impostor:
            gap = min(genuine) - max(impostor)
            print(f"  separation (min genuine - max impostor): {gap:+.3f}  "
                  f"({'clean separation' if gap > 0 else 'OVERLAP -- thresholds will need care'})")
        print()

    # --- Face-match by quality variant (does blur/glare break matching?) ---
    for label, attr in (("SFace", "face_embedding"), ("ArcFace", "face_embedding_arcface")):
        faces_this_model = [r for r in records if getattr(r, attr) is not None]
        if not faces_this_model:
            continue
        print(f"=== Genuine-pair similarity by variant of the non-base image [{label}] ===")
        by_variant: dict[str, list[float]] = {"blured": [], "light_reflection": []}
        base_by_identity = {r.identity: r for r in faces_this_model if r.variant == "base"}
        for r in faces_this_model:
            if r.variant in by_variant and r.identity in base_by_identity:
                sim = cosine_sim(getattr(r, attr), getattr(base_by_identity[r.identity], attr))
                by_variant[r.variant].append(sim)
        for variant, sims in by_variant.items():
            summarize(f"base vs {variant}", sims)
        print()

    # --- Image quality heuristics by variant bucket ---
    print("=== Image quality heuristics by variant (for blur/glare threshold calibration) ===")
    for variant in ("base", "blured", "light_reflection"):
        blur_scores = [r.blur_score for r in records if r.variant == variant]
        glare_ratios = [r.glare_ratio for r in records if r.variant == variant]
        print(f" [{variant}]")
        summarize("laplacian blur score (lower = blurrier)", blur_scores)
        summarize("overexposed-pixel ratio (higher = more glare)", glare_ratios)
    print()

    # --- OCR self-consistency across quality variants (no ground truth needed) ---
    # Pairs where either side is empty are reported separately rather than
    # folded into the similarity stats -- an empty/empty pair trivially scores
    # 100 on rapidfuzz.ratio, which would otherwise silently inflate the
    # "consistency" numbers.
    ocr_base_by_identity: dict[str, list[ImageRecord]] = {}
    for r in records:
        if r.variant == "base":
            ocr_base_by_identity.setdefault(r.identity, []).append(r)

    for label, attr in (("tesseract-preprocessed", "ocr_text_pre"), ("paddleocr", "ocr_text_paddle")):
        print(f"=== OCR text self-consistency [{label}]: base ID-front vs degraded variant ===")
        consistency_scores: list[float] = []
        empty_pair_count = 0
        for r in records:
            if r.variant in ("blured", "light_reflection") and r.identity in ocr_base_by_identity:
                bases = ocr_base_by_identity[r.identity]
                base_nonempty = any(getattr(b, attr) for b in bases)
                this_nonempty = bool(getattr(r, attr))
                if not base_nonempty or not this_nonempty:
                    empty_pair_count += 1
                    status = "SKIPPED (one or both sides empty)"
                else:
                    best = max(fuzz.ratio(getattr(r, attr), getattr(base, attr)) for base in bases)
                    consistency_scores.append(best)
                    status = f"{best:.1f}"
                print(f"  identity={r.identity} variant={r.variant} file={r.path.name} "
                      f"best-match-to-base={status} (base non-empty={base_nonempty}, this non-empty={this_nonempty})")
        print(f"  -> {empty_pair_count} pair(s) skipped for empty text; "
              f"{len(consistency_scores)} scored pair(s)")
        summarize("scored consistency", consistency_scores)
        print()

    print("=== OCR output per image, all engines (manually eyeball against the source photo -- not persisted) ===")
    for r in records:
        preview_raw = r.ocr_text_raw.replace("\n", " | ")[:80]
        preview_pre = r.ocr_text_pre.replace("\n", " | ")[:80]
        preview_paddle = r.ocr_text_paddle.replace("\n", " | ")[:80]
        print(f"  [{r.identity}/{r.variant}] {r.path.name}: blur={r.blur_score:.0f} "
              f"glare={r.glare_ratio:.3f} sface={'Y' if r.face_embedding is not None else 'N'} "
              f"arcface={'Y' if r.face_embedding_arcface is not None else 'N'} "
              f"doc_crop={'Y' if r.doc_crop_used else 'N'}")
        print(f"      tesseract-raw='{preview_raw}'")
        print(f"      tesseract-pre='{preview_pre}'")
        print(f"      paddleocr='{preview_paddle}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
