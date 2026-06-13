"""Training pipeline entry point. Run: uv run python -m pipelines.training.run"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_FEATURES_PATH = Path(__file__).parent.parent.parent / "data" / "features" / "features.parquet"


def _make_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def main() -> None:
    from pipelines.training.train_match_score import TrainingGateError, train_match_score
    from pipelines.training.train_price import train_price_recommender
    from pipelines.training.train_ranker import train_ride_ranker

    logger.info("=== Training Pipeline Start ===")

    if not _FEATURES_PATH.exists():
        logger.error("Features not found: %s — run pipelines.features.run first", _FEATURES_PATH)
        sys.exit(1)

    features_df: pd.DataFrame = pd.read_parquet(_FEATURES_PATH)
    logger.info("Loaded %d feature vectors from %s", len(features_df), _FEATURES_PATH)

    version = _make_version()
    logger.info("Training version: %s", version)

    # Match score MUST succeed first — gate enforced, others are blocked on this
    try:
        logger.info("--- Training match_score ---")
        train_match_score(features_df, version)
    except TrainingGateError as exc:
        logger.error("GATE FAILED: %s", exc)
        sys.exit(1)

    logger.info("--- Training ride_ranker ---")
    train_ride_ranker(features_df, version)

    logger.info("--- Training price_recommender ---")
    train_price_recommender(features_df, version)

    logger.info("--- Uploading to Supabase Storage ---")
    from pipelines.training.upload import upload_all_models
    upload_all_models(version)

    logger.info("=== Training Pipeline Complete (version: %s) ===", version)


if __name__ == "__main__":
    main()
