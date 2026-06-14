from supabase import create_client

from app.core.config import settings

_SIGNED_URL_EXPIRY = 3600  # 60 minutes


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def generate_signed_url(bucket: str, path: str, expires_in: int = _SIGNED_URL_EXPIRY) -> str | None:
    if not path:
        return None
    sb = _supabase()
    try:
        resp = sb.storage.from_(bucket).create_signed_url(path, expires_in)
        return resp.get("signedURL") or resp.get("signed_url")
    except Exception:
        return None


def get_identity_document_urls(submission: dict) -> dict:
    urls: dict = {}
    for field, key in [("front_id_path", "front_id"), ("back_id_path", "back_id"), ("license_path", "license")]:
        path = submission.get(field)
        if path:
            urls[key] = generate_signed_url("identity-documents", path)
    return urls


def upload_file(bucket: str, path: str, data: bytes, content_type: str) -> str:
    sb = _supabase()
    sb.storage.from_(bucket).upload(path, data, {"content-type": content_type, "upsert": "true"})
    return path
