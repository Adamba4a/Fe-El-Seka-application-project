from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache(maxsize=1)
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            # A short cap keeps a degraded R2 connection from tying up an API
            # worker forever, but 3 seconds is too aggressive for cold or
            # cross-region connections in production.
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
