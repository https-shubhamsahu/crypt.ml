from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.train_ml import split_features, to_model_schema


DEFAULT_DATA_PATH = Path("data/training_transactions.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview transformed training features before model training.")
    parser.add_argument(
        "--data-path",
        default=str(DEFAULT_DATA_PATH),
        help="Path to source CSV dataset.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10,
        help="Number of transformed rows to preview.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_path}")

    raw_df = pd.read_csv(data_path)
    transformed_df = to_model_schema(raw_df)
    features, target = split_features(transformed_df)

    preview_rows = max(1, args.rows)

    print("=" * 80)
    print("Feature Mapping Preview")
    print("=" * 80)
    print(f"Source path: {data_path}")
    print(f"Raw shape: {raw_df.shape}")
    print(f"Transformed shape: {transformed_df.shape}")
    print(f"Feature columns: {list(features.columns)}")
    print(f"Label distribution: {target.value_counts().to_dict()}")
    print("-" * 80)
    print(features.head(preview_rows).to_string(index=False))
    print("-" * 80)
    print("Label preview:")
    print(target.head(preview_rows).to_string(index=False))


if __name__ == "__main__":
    main()
