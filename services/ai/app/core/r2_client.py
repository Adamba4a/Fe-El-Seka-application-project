from functools import lru_cache

import boto3
from botocore.config import Config

from app.config import get_settings


@lru_cache(maxsize=1)
def get_r2_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
