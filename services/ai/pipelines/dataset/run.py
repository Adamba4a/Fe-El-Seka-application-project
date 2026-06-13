"""Dataset pipeline entry point. Run: uv run python -m pipelines.dataset.run"""
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "raw" / "rides.parquet"
_MIN_RECORDS = 100_000
_MIN_ZONES = 18
_POSITIVE_RATE_MIN = 0.25
_POSITIVE_RATE_MAX = 0.55


def validate(df: pd.DataFrame) -> None:
    if len(df) < _MIN_RECORDS:
        raise ValueError(f"Expected >= {_MIN_RECORDS} records, got {len(df)}")
    null_count = df.isnull().sum().sum()
    if null_count > 0:
        raise ValueError(f"Dataset contains {null_count} null values")
    n_zones = df["origin_zone"].nunique()
    if n_zones < _MIN_ZONES:
        raise ValueError(f"Expected >= {_MIN_ZONES} distinct origin zones, got {n_zones}")
    rate = df["match_label"].mean()
    if not (_POSITIVE_RATE_MIN <= rate <= _POSITIVE_RATE_MAX):
        logger.warning("Match label positive rate %.1f%% is outside expected 25-55%% window", rate * 100)


def main() -> None:
    from pipelines.dataset.ingest_osm import download_cairo_graph
    from pipelines.dataset.generate_rides import generate_rides

    logger.info("=== Dataset Pipeline Start ===")

    logger.info("Step 1: OSM road network ingestion")
    download_cairo_graph()

    logger.info("Step 2: Synthetic ride generation")
    df = generate_rides(n=_MIN_RECORDS)

    logger.info("Step 3: Validation")
    try:
        validate(df)
    except ValueError as exc:
        logger.error("Validation failed: %s", exc)
        sys.exit(1)

    logger.info("Step 4: Writing %d records to %s", len(df), _OUTPUT_PATH)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUTPUT_PATH, index=False)

    logger.info("=== Dataset Pipeline Complete ===")
    logger.info("Records: %d | Origin zones: %d | Match rate: %.1f%%",
                len(df), df["origin_zone"].nunique(), df["match_label"].mean() * 100)


if __name__ == "__main__":
    main()
