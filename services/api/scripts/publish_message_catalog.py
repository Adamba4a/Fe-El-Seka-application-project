"""
Publish apps/main/messages/{en,ar}.json to the R2-hosted message catalog
that messages-loader.ts actually reads at runtime (see
specs/017-arabic-rtl-localization/contracts/message-catalog.md).

Editing the repo files alone does NOT change what the running app shows —
the loader fetches from Storage/R2 and only falls back to the bundled repo
file if that fetch fails. This script is the missing publish step.

Run (local dev, against services/api/.env's R2 creds):
    uv run python scripts/publish_message_catalog.py

Run for prod (do NOT run against prod until explicitly told to):
    uv run python scripts/publish_message_catalog.py --env-file ../../.env.prod
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings  # noqa: E402
from app.core.r2_client import get_r2_client  # noqa: E402

_BUCKET = "app-content"
_MESSAGES_DIR = Path(__file__).parent.parent.parent.parent / "apps" / "main" / "messages"
_LOCALES = ["en", "ar"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", default=None, help="Path to an alternate .env file (default: services/api/.env)"
    )
    args = parser.parse_args()

    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()  # noqa: F841
    r2 = get_r2_client()
    version = datetime.now(timezone.utc).isoformat()

    for locale in _LOCALES:
        src = _MESSAGES_DIR / f"{locale}.json"
        messages = json.loads(src.read_text(encoding="utf-8"))
        payload = {"locale": locale, "version": version, "messages": messages}
        key = f"messages/{locale}.json"
        r2.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Published {_BUCKET}/{key} (version={version})")


if __name__ == "__main__":
    main()
