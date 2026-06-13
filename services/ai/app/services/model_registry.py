import json
import logging
import tempfile
from pathlib import Path

from supabase import Client, create_client

from app.config import get_settings

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    pass


def _version_to_path(version: str) -> str:
    """Replace colons with hyphens for Storage path safety."""
    return version.replace(":", "-")


class ModelRegistry:
    def __init__(self) -> None:
        s = get_settings()
        self._client: Client = create_client(s.supabase_url, s.supabase_service_role_key)
        self._bucket = s.model_registry_bucket

    def get_latest_version(self, model_type: str) -> str:
        path = f"{model_type}/latest.json"
        try:
            data = self._client.storage.from_(self._bucket).download(path)
            return json.loads(data)["version"]
        except Exception as exc:
            raise RegistryError(f"Failed to fetch latest version for {model_type}: {exc}") from exc

    def download_model(self, model_type: str, version: str) -> Path:
        version_path = _version_to_path(version)
        remote = f"{model_type}/{version_path}/model.joblib"
        try:
            data = self._client.storage.from_(self._bucket).download(remote)
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
                self._client.storage.from_(self._bucket).upload(
                    remote, f.read(), {"content-type": "application/octet-stream"}
                )
            logger.info("Uploaded %s model v%s", model_type, version)
        except Exception as exc:
            raise RegistryError(f"Failed to upload {model_type} v{version}: {exc}") from exc

    def upload_metadata(self, model_type: str, version: str, metadata: dict) -> None:
        version_path = _version_to_path(version)
        remote = f"{model_type}/{version_path}/metadata.json"
        try:
            payload = json.dumps(metadata).encode()
            self._client.storage.from_(self._bucket).upload(
                remote, payload, {"content-type": "application/json"}
            )
        except Exception as exc:
            raise RegistryError(f"Failed to upload metadata for {model_type} v{version}: {exc}") from exc

    def write_latest(self, model_type: str, version: str) -> None:
        remote = f"{model_type}/latest.json"
        payload = json.dumps({"version": version}).encode()
        try:
            # Try update first; fall back to upload for new bucket paths
            try:
                self._client.storage.from_(self._bucket).update(
                    remote, payload, {"content-type": "application/json"}
                )
            except Exception:
                self._client.storage.from_(self._bucket).upload(
                    remote, payload, {"content-type": "application/json"}
                )
        except Exception as exc:
            raise RegistryError(f"Failed to write latest.json for {model_type}: {exc}") from exc
