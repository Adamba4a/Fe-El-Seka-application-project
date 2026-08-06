FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# ---- runner ----
FROM python:3.11-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr tesseract-ocr-ara \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appuser && useradd --uid 1001 --gid 1001 --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ /app/app/
COPY pipelines/ /app/pipelines/

# Face-match model weights are gitignored (large binaries) -- fetch them from
# the OpenCV Zoo at build time instead of vendoring in the repo.
RUN mkdir -p /app/app/models/weights && \
    curl -fsSL -o /app/app/models/weights/face_detection_yunet_2023mar.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx && \
    curl -fsSL -o /app/app/models/weights/face_recognition_sface_2021dec.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
