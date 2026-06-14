"""Feature engineering pipeline entry point. Run: uv run python -m pipelines.features.run"""
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_INPUT_PATH = Path(__file__).parent.parent.parent / "data" / "raw" / "rides.parquet"
_OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "features" / "features.parquet"


def main() -> None:
    from pipelines.features.engineer import engineer_features

    logger.info("=== Feature Engineering Pipeline Start ===")

    if not _INPUT_PATH.exists():
        logger.error("Input not found: %s — run pipelines.dataset.run first", _INPUT_PATH)
        sys.exit(1)

    rides_df = pd.read_parquet(_INPUT_PATH)
    logger.info("Loaded %d ride records from %s", len(rides_df), _INPUT_PATH)

    features_df = engineer_features(rides_df)
    logger.info("Engineered %d feature vectors", len(features_df))

    # Validate: no NaN, no Inf
    if features_df.isnull().any().any():
        logger.error("Feature matrix contains NaN values")
        sys.exit(1)
    if np.isinf(features_df.select_dtypes("number").values).any():
        logger.error("Feature matrix contains Inf values")
        sys.exit(1)

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(_OUTPUT_PATH, index=False)

    logger.info("=== Feature Engineering Pipeline Complete ===")
    logger.info("Shape: %s | Columns: %s", features_df.shape, list(features_df.columns))


if __name__ == "__main__":
    main()
