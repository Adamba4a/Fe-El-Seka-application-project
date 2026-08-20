from pathlib import Path

import cv2
import numpy as np

DET_MODEL = "face_detection_yunet_2023mar.onnx"
REC_MODEL = "face_recognition_sface_2021dec.onnx"
DET_SCORE_THRESHOLD = 0.7


def load_face_models(weights_dir: Path) -> tuple[cv2.FaceDetectorYN, cv2.FaceRecognizerSF]:
    detector = cv2.FaceDetectorYN.create(
        str(weights_dir / DET_MODEL), "", (320, 320), score_threshold=DET_SCORE_THRESHOLD
    )
    recognizer = cv2.FaceRecognizerSF.create(str(weights_dir / REC_MODEL), "")
    return detector, recognizer


def detect_and_align_face(
    img_bgr: np.ndarray,
    detector: cv2.FaceDetectorYN,
    recognizer: cv2.FaceRecognizerSF,
) -> np.ndarray | None:
    """Detects the largest face and returns SFace's canonical 112x112 aligned crop."""
    detector.setInputSize((img_bgr.shape[1], img_bgr.shape[0]))
    _, faces = detector.detect(img_bgr)
    if faces is None or len(faces) == 0:
        return None
    largest = max(faces, key=lambda f: f[2] * f[3])
    return recognizer.alignCrop(img_bgr, largest)


def compute_embedding(aligned_bgr: np.ndarray, recognizer: cv2.FaceRecognizerSF) -> np.ndarray:
    return recognizer.feature(aligned_bgr)


def match_score(
    embedding_a: np.ndarray, embedding_b: np.ndarray, recognizer: cv2.FaceRecognizerSF
) -> float:
    return float(
        recognizer.match(embedding_a, embedding_b, cv2.FaceRecognizerSF_FR_COSINE)
    )


def face_match(
    id_img_bgr: np.ndarray,
    selfie_img_bgr: np.ndarray,
    detector: cv2.FaceDetectorYN,
    recognizer: cv2.FaceRecognizerSF,
) -> tuple[float | None, bool, bool]:
    """Returns (cosine_similarity_or_None, id_face_detected, selfie_face_detected)."""
    id_aligned = detect_and_align_face(id_img_bgr, detector, recognizer)
    selfie_aligned = detect_and_align_face(selfie_img_bgr, detector, recognizer)
    id_detected = id_aligned is not None
    selfie_detected = selfie_aligned is not None
    if id_aligned is None or selfie_aligned is None:
        return None, id_detected, selfie_detected

    emb_a = compute_embedding(id_aligned, recognizer)
    emb_b = compute_embedding(selfie_aligned, recognizer)
    return match_score(emb_a, emb_b, recognizer), id_detected, selfie_detected
