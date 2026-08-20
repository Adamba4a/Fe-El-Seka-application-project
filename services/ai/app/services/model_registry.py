import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.r2_client import get_r2_client

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    pass


def _version_to_path(version: str) -> str:
    """Replace colons with hyphens for Storage path safety."""
    return version.replace(":", "-")


class ModelRegistry:
    def __init__(self) -> None:
        s = get_settings()
        self._client = get_r2_client()
        self._bucket = s.model_registry_bucket

    def get_latest_version(self, model_type: str) -> str:
        path = f"{model_type}/latest.json"
        try:
            data = self._client.get_object(Bucket=self._bucket, Key=path)["Body"].read()
            return str(json.loads(data)["version"])
        except Exception as exc:
            raise RegistryError(f"Failed to fetch latest version for {model_type}: {exc}") from exc

    def download_model(self, model_type: str, version: str) -> Path:
        version_path = _version_to_path(version)
        remote = f"{model_type}/{version_path}/model.joblib"
        try:
            data = self._client.get_object(Bucket=self._bucket, Key=remote)["Body"].read()
            tmp = tempfile.NamedTemporaryFile(suffix=".joblib", delete=False)
            tmp.write(data)
            tmp.flush()
            return Path(tmp.name)
        except Exception as exc:
            raise RegistryError(f"Failed to download {model_type} v{version}: {exc}") from exc

    def upload_model(self, model_type: str, version: str, local_path: Path) -> None:
        version_path = _version_to_path(version)
        remote = f"{model_type}/{version_path}/model.joblib"
        try:
            with open(local_path, "rb") as f:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=remote,
                    Body=f.read(),
                    ContentType="application/octet-stream",
                )
            logger.info("Uploaded %s model v%s", model_type, version)
        except Exception as exc:
            raise RegistryError(f"Failed to upload {model_type} v{version}: {exc}") from exc

    def upload_metadata(self, model_type: str, version: str, metadata: dict[str, Any]) -> None:
        version_path = _version_to_path(version)
        remote = f"{model_type}/{version_path}/metadata.json"
        try:
            payload = json.dumps(metadata).encode()
            self._client.put_object(
                Bucket=self._bucket, Key=remote, Body=payload, ContentType="application/json"
            )
        except Exception as exc:
            raise RegistryError(
                f"Failed to upload metadata for {model_type} v{version}: {exc}"
            ) from exc

    def write_latest(self, model_type: str, version: str) -> None:
        remote = f"{model_type}/latest.json"
        payload = json.dumps({"version": version}).encode()
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=remote, Body=payload, ContentType="application/json"
            )
        except Exception as exc:
            raise RegistryError(f"Failed to write latest.json for {model_type}: {exc}") from exc

    def get_candidate_version(self, model_type: str) -> str | None:
        """Returns the currently shadow/rollout candidate's version for
        model_type, or None if no candidate.json exists (the common case
        pre-feature and between rollout cycles)."""
        path = f"{model_type}/candidate.json"
        try:
            data = self._client.get_object(Bucket=self._bucket, Key=path)["Body"].read()
            return str(json.loads(data)["version"])
        except Exception:
            return None

    def write_candidate(self, model_type: str, version: str) -> None:
        remote = f"{model_type}/candidate.json"
        payload = json.dumps({"version": version}).encode()
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=remote, Body=payload, ContentType="application/json"
            )
        except Exception as exc:
            raise RegistryError(f"Failed to write candidate.json for {model_type}: {exc}") from exc

    def clear_candidate(self, model_type: str) -> None:
        """Removes candidate.json, e.g. on rejection, unfavorable shadow
        burn-in, or rollback. Not an error if it never existed."""
        remote = f"{model_type}/candidate.json"
        try:
            self._client.delete_object(Bucket=self._bucket, Key=remote)
        except Exception as exc:
            logger.warning("Failed to clear candidate.json for %s: %s", model_type, exc)
