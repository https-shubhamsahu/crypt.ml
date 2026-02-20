from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.agentic_aml import AMLOrchestratorA2A, SARReportGenerator, batch_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local RAW+SAR+A2A AML demo pipeline.")
    parser.add_argument("--data-path", default="data/training_transactions.csv", help="Input CSV path.")
    parser.add_argument("--max-rows", default=100, type=int, help="Number of rows to process.")
    parser.add_argument("--report-path", default="artifacts/agentic_report.json", help="Output report file path.")
    return parser.parse_args()


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    if "transaction_amount" in normalized.columns and "amount" not in normalized.columns:
        normalized["amount"] = normalized["transaction_amount"]

    if "src_account" not in normalized.columns:
        normalized["src_account"] = [f"ACC_{idx:06d}" for idx in range(len(normalized))]
    if "dst_account" not in normalized.columns:
        normalized["dst_account"] = [f"ACC_{idx + 1000:06d}" for idx in range(len(normalized))]

    if "tx_count_last_hour" not in normalized.columns:
        normalized["tx_count_last_hour"] = 1

    return normalized


def main() -> None:
    args = parse_args()
    data_path = Path(args.data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_path}")

    df = pd.read_csv(data_path)
    df = normalize_df(df)
    subset = df.head(max(1, args.max_rows))

    orchestrator = AMLOrchestratorA2A()
    decisions = [orchestrator.process(row.to_dict()) for _, row in subset.iterrows()]

    report = SARReportGenerator.build_report(decisions[0], subset.iloc[0].to_dict())
    metrics = batch_metrics(decisions)

    output = {
        "summary": metrics,
        "sample_report": report,
    }

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Processed rows: {metrics['total']}")
    print(f"Decision counts: {metrics['decision_counts']}")
    print(f"Mean risk: {metrics['mean_risk']}")
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
