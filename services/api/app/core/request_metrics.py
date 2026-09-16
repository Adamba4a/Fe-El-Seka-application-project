from __future__ import annotations

import math
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

_UUID = re.compile(r"/[0-9a-f]{8}-[0-9a-f-]{27,36}(?=/|$)", re.IGNORECASE)
_NUMBER = re.compile(r"/\d+(?=/|$)")
_WINDOW_SECONDS = 15 * 60
_MAX_SAMPLES = 10_000
_MAX_ENDPOINTS = 30


@dataclass(frozen=True)
class RequestSample:
    at: float
    path: str
    method: str
    status_code: int
    duration_ms: float


def normalize_path(path: str) -> str:
    """Return a bounded, identifier-free route label for aggregate metrics."""
    if path.startswith("/api/internal/metrics"):
        return "/api/internal/metrics"
    if not path.startswith(("/api/", "/health")):
        return "/other"
    # Allow known API prefixes only. Unknown paths must not create unbounded
    # labels from user-controlled URLs.
    known = (
        "/api/auth",
        "/api/profiles",
        "/api/verification",
        "/api/vehicles",
        "/api/v1",
        "/api/routes",
        "/api/geocode",
        "/api/groups",
        "/api/wallet",
        "/api/admin",
        "/api/support",
        "/api/health",
        "/health",
    )
    if not path.startswith(known):
        return "/other"
    path = _UUID.sub("/{id}", path)
    path = _NUMBER.sub("/{id}", path)
    # Route templates are safe; for raw paths retain only their stable service
    # and resource prefix. This prevents an unmatched URL such as
    # /api/v1/rides/an-email-or-token from ending up in an operator response.
    if "{" in path:
        return path
    parts = [part for part in path.split("/") if part]
    if len(parts) <= 3:
        return path
    if len(parts) == 4 and parts[-1] == "{id}":
        return path
    return "/" + "/".join(parts[:3]) + "/{path}"


class RequestMetrics:
    def __init__(self, now=time.monotonic) -> None:
        self._now = now
        self._samples: deque[RequestSample] = deque(maxlen=_MAX_SAMPLES)
        self._inflight = 0
        self._lock = threading.Lock()

    def begin(self) -> None:
        with self._lock:
            self._inflight += 1

    def record(self, path: str, method: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)
            self._samples.append(
                RequestSample(self._now(), normalize_path(path), method, status_code, round(duration_ms, 2))
            )

    def abandon(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    def snapshot(self, pool=None) -> dict:
        now = self._now()
        cutoff = now - _WINDOW_SECONDS
        with self._lock:
            samples = [sample for sample in self._samples if sample.at >= cutoff]
            inflight = self._inflight
        durations = sorted(sample.duration_ms for sample in samples)
        total = len(samples)
        errors = sum(sample.status_code >= 500 for sample in samples)
        client_errors = sum(400 <= sample.status_code < 500 for sample in samples)
        endpoint_samples: dict[tuple[str, str], list[RequestSample]] = {}
        for sample in samples:
            endpoint_samples.setdefault((sample.method, sample.path), []).append(sample)
        endpoints = []
        for (method, path), group in endpoint_samples.items():
            group_durations = sorted(item.duration_ms for item in group)
            endpoints.append(
                {
                    "method": method,
                    "path": path,
                    "requests": len(group),
                    "errors_5xx": sum(item.status_code >= 500 for item in group),
                    "p95_ms": _percentile(group_durations, 0.95),
                }
            )
        endpoints.sort(key=lambda item: (item["p95_ms"], item["requests"]), reverse=True)
        database = None
        if pool is not None:
            database = {
                "connections_open": pool.get_size(),
                "connections_idle": pool.get_idle_size(),
                "connections_max": pool.get_max_size(),
            }
        observed_seconds = min(_WINDOW_SECONDS, max(1, now - samples[0].at)) if samples else 1
        return {
            "window_seconds": _WINDOW_SECONDS,
            "instance": os.getenv("BUNNYNET_MC_PODID", "local"),
            "request_count": total,
            "requests_per_second": round(total / observed_seconds, 4),
            "errors_5xx": errors,
            "errors_4xx": client_errors,
            "error_rate_5xx": round(errors / total, 4) if total else 0,
            "p50_ms": _percentile(durations, 0.5),
            "p95_ms": _percentile(durations, 0.95),
            "inflight": inflight,
            "database": database,
            "slowest_endpoints": endpoints[:_MAX_ENDPOINTS],
        }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return values[min(len(values) - 1, math.ceil(len(values) * percentile) - 1)]


request_metrics = RequestMetrics()
