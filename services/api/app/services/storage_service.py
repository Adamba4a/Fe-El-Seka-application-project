from app.core.r2_client import get_r2_client

_SIGNED_URL_EXPIRY = 3600  # 60 minutes


def generate_signed_url(
    bucket: str, path: str, expires_in: int = _SIGNED_URL_EXPIRY
) -> str | None:
    if not path:
        return None
    try:
        return get_r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": path},
            ExpiresIn=expires_in,
        )
    except Exception:
        return None


def get_identity_document_urls(submission: dict) -> dict:
    urls: dict = {}
    for field, key in [
        ("front_id_path", "front_id"),
        ("back_id_path", "back_id"),
        ("license_path", "license"),
        ("selfie_path", "selfie"),
    ]:
        path = submission.get(field)
        if path:
            urls[key] = generate_signed_url("identity-documents", path)
    return urls


def download_file(bucket: str, path: str) -> bytes | None:
    if not path:
        return None
    try:
        resp = get_r2_client().get_object(Bucket=bucket, Key=path)
        return resp["Body"].read()
    except Exception:
        return None


def upload_file(bucket: str, path: str, data: bytes, content_type: str) -> str:
    get_r2_client().put_object(
        Bucket=bucket, Key=path, Body=data, ContentType=content_type
    )
    return path
