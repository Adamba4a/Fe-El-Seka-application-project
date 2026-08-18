"""
One-time (safely re-runnable) copy of all objects from Supabase Storage to
their Cloudflare R2 counterparts, preserving keys exactly.

Copies all 6 buckets: identity-documents, profile-photos, app-content,
topup-proofs, training-datasets, model-registry.

Idempotent: an object that already exists in R2 at the same key is skipped
by default (use --overwrite to re-copy anyway). Safe to re-run for prod
later without re-transferring everything that already succeeded.

Run (local dev, against services/api/.env's local Supabase + R2 creds):
    uv run python scripts/migrate_supabase_storage_to_r2.py

Run for prod (once ready — do NOT run against prod until explicitly told to):
    uv run python scripts/migrate_supabase_storage_to_r2.py --env-file ../../.env.prod
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.r2_client import get_r2_client  # noqa: E402

_BUCKETS = [
    "identity-documents",
    "profile-photos",
    "app-content",
    "topup-proofs",
    "training-datasets",
    "model-registry",
]

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


def _list_all_objects(sb, bucket: str, prefix: str = "") -> list[dict]:
    """Recursively flattens Supabase Storage's hierarchical list() into a
    flat list of {key, content_type} dicts. Supabase's list() returns one
    level at a time; entries with id=None/metadata=None are sub-folders
    (recurse into them), entries with metadata are actual files (leaf)."""
    entries = sb.storage.from_(bucket).list(prefix, {"limit": 1000}) or []
    results: list[dict] = []
    for entry in entries:
        name = entry.get("name")
        if not name:
            continue
        full_path = f"{prefix}/{name}" if prefix else name
        if entry.get("id") is None and entry.get("metadata") is None:
            results.extend(_list_all_objects(sb, bucket, full_path))
        else:
            content_type = (entry.get("metadata") or {}).get("mimetype") or _DEFAULT_CONTENT_TYPE
            results.append({"key": full_path, "content_type": content_type})
    return results


def _object_exists_in_r2(r2, bucket: str, key: str) -> bool:
    try:
        r2.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def migrate_bucket(sb, r2, bucket: str, overwrite: bool) -> dict:
    objects = _list_all_objects(sb, bucket)
    copied = skipped = failed = 0
    for obj in objects:
        key = obj["key"]
        if not overwrite and _object_exists_in_r2(r2, bucket, key):
            skipped += 1
            continue
        try:
            data = sb.storage.from_(bucket).download(key)
            r2.put_object(Bucket=bucket, Key=key, Body=data, ContentType=obj["content_type"])
            copied += 1
        except Exception as exc:
            failed += 1
            print(f"  FAILED  {bucket}/{key}: {exc}")
    return {"bucket": bucket, "total": len(objects), "copied": copied, "skipped": skipped, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", default=None, help="Path to an alternate .env file (default: services/api/.env)"
    )
    parser.add_argument("--overwrite", action="store_true", help="Re-copy objects that already exist in R2")
    parser.add_argument(
        "--bucket", action="append", help="Limit to specific bucket(s); repeatable. Default: all 6."
    )
    args = parser.parse_args()

    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r2 = get_r2_client()

    buckets = args.bucket or _BUCKETS
    print(f"Migrating {len(buckets)} bucket(s): {', '.join(buckets)}")
    print(f"Supabase: {settings.supabase_url}")
    print(f"R2 endpoint: {settings.r2_endpoint_url}")
    print(f"Mode: {'overwrite' if args.overwrite else 'skip-existing'}\n")

    grand_total = grand_copied = grand_skipped = grand_failed = 0
    for bucket in buckets:
        print(f"[{bucket}]")
        result = migrate_bucket(sb, r2, bucket, args.overwrite)
        print(
            f"  total={result['total']} copied={result['copied']} "
            f"skipped={result['skipped']} failed={result['failed']}\n"
        )
        grand_total += result["total"]
        grand_copied += result["copied"]
        grand_skipped += result["skipped"]
        grand_failed += result["failed"]

    print(f"TOTAL: total={grand_total} copied={grand_copied} skipped={grand_skipped} failed={grand_failed}")
    if grand_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
