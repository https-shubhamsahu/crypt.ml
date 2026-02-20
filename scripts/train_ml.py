from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Tuple

import joblib
import pandas as pd
import shap
from sklearn.metrics import classification_report, roc_auc_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


DATA_PATH = Path("data/training_transactions.csv")
ARTIFACT_DIR = Path("artifacts")
MODEL_PATH = ARTIFACT_DIR / "ml_model.joblib"
METADATA_PATH = ARTIFACT_DIR / "ml_model_metadata.json"
SHAP_PATH = ARTIFACT_DIR / "ml_model_shap_summary.json"

MODEL_FEATURES = [
    "transaction_amount",
    "tx_count_last_hour",
    "has_upi",
    "nlp_signal",
]
UNIFIED_REQUIRED = set(MODEL_FEATURES + ["label"])
PAYSIM_REQUIRED = {"amount", "step", "nameOrig", "isFraud"}
AML_CFT_REQUIRED = {
    "time",
    "date",
    "sender_account",
    "receiver_account",
    "amount",
    "payment_currency",
    "received_currency",
    "sender_bank_location",
    "receiver_bank_location",
    "payment_type",
    "is_laundering",
    "laundering_type",
}


def load_training_data(data_path: Path) -> pd.DataFrame:
    if data_path.exists():
        return pd.read_csv(data_path)

    raise FileNotFoundError(
        f"Dataset not found at {data_path}. Put your local CSV there or pass --data-path."
    )


def to_model_schema(df: pd.DataFrame) -> pd.DataFrame:
    columns = set(df.columns)
    if UNIFIED_REQUIRED.issubset(columns):
        clean = df.copy()
        clean = clean.dropna(subset=["transaction_amount", "tx_count_last_hour", "has_upi", "nlp_signal", "label"])
        clean["label"] = clean["label"].astype(int)
        clean["has_upi"] = clean["has_upi"].astype(int)
        return clean

    if PAYSIM_REQUIRED.issubset(columns):
        transformed = pd.DataFrame()
        transformed["transaction_amount"] = df["amount"].astype(float)
        transformed["tx_count_last_hour"] = (
            df.groupby(["nameOrig", "step"])["amount"].transform("count").astype(int)
        )
        transformed["has_upi"] = df["nameOrig"].notna().astype(int)

        if "transaction_note" in df.columns:
            transformed["nlp_signal"] = (
                df["transaction_note"].fillna("").str.len().clip(upper=100).astype(float)
            )
        else:
            transformed["nlp_signal"] = 0.0

        transformed["label"] = df["isFraud"].astype(int)
        transformed = transformed.dropna()
        return transformed

    lower_to_original = {col.strip().lower(): col for col in df.columns}
    if AML_CFT_REQUIRED.issubset(set(lower_to_original.keys())):
        transformed = pd.DataFrame()

        date_col = lower_to_original["date"]
        time_col = lower_to_original["time"]
        sender_col = lower_to_original["sender_account"]
        amount_col = lower_to_original["amount"]
        payment_curr_col = lower_to_original["payment_currency"]
        received_curr_col = lower_to_original["received_currency"]
        sender_loc_col = lower_to_original["sender_bank_location"]
        receiver_loc_col = lower_to_original["receiver_bank_location"]
        payment_type_col = lower_to_original["payment_type"]
        label_col = lower_to_original["is_laundering"]
        laundering_type_col = lower_to_original["laundering_type"]

        combined_ts = pd.to_datetime(
            df[date_col].astype(str).str.strip() + " " + df[time_col].astype(str).str.strip(),
            errors="coerce",
        )
        hour_bucket = combined_ts.dt.floor("h")

        transformed["transaction_amount"] = pd.to_numeric(df[amount_col], errors="coerce")
        transformed["tx_count_last_hour"] = (
            df.groupby([df[sender_col], hour_bucket])[amount_col].transform("count")
        )
        transformed["has_upi"] = df[sender_col].notna().astype(int)

        payment_type_risk = (
            df[payment_type_col]
            .astype(str)
            .str.lower()
            .map(
                {
                    "cross-border": 30.0,
                    "cash deposit": 18.0,
                    "cheque": 12.0,
                    "ach": 10.0,
                    "credit card": 8.0,
                    "debit card": 6.0,
                }
            )
            .fillna(5.0)
        )

        cross_currency = (
            df[payment_curr_col].astype(str).str.lower().str.strip()
            != df[received_curr_col].astype(str).str.lower().str.strip()
        ).astype(float) * 20.0

        cross_border = (
            df[sender_loc_col].astype(str).str.lower().str.strip()
            != df[receiver_loc_col].astype(str).str.lower().str.strip()
        ).astype(float) * 22.0

        laundering_text_score = (
            df[laundering_type_col]
            .astype(str)
            .str.lower()
            .str.contains("fan_out|fan-in|fan_in|group|layer|cross", regex=True)
            .astype(float)
            * 18.0
        )

        transformed["nlp_signal"] = (
            payment_type_risk + cross_currency + cross_border + laundering_text_score
        ).clip(0.0, 100.0)

        transformed["label"] = pd.to_numeric(df[label_col], errors="coerce").fillna(0).astype(int)
        transformed = transformed.dropna(subset=["transaction_amount", "tx_count_last_hour", "has_upi", "nlp_signal", "label"])
        return transformed

    raise ValueError(
        "Unsupported training schema. Provide unified columns "
        f"{sorted(UNIFIED_REQUIRED)}, PaySim columns {sorted(PAYSIM_REQUIRED)}, "
        "or AML-CFT columns [Time, Date, Sender_account, Receiver_account, Amount, "
        "Payment_currency, Received_currency, Sender_bank_location, Receiver_bank_location, "
        "Payment_type, Is_laundering, Laundering_type]."
    )


def split_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    features = df[MODEL_FEATURES]
    target = df["label"]
    return features, target


def train_model(data_path: Path, target_recall: float) -> None:
    raw_df = load_training_data(data_path=data_path)
    df = to_model_schema(raw_df)

    if df.empty:
        raise ValueError("Training dataset produced 0 usable rows after preprocessing.")

    if len(df) < 20:
        raise ValueError(
            "Training dataset is too small for stable train/test split. "
            "Use at least 20 rows (preferably much more)."
        )

    class_counts = df["label"].value_counts().to_dict()
    if len(class_counts) < 2:
        raise ValueError("Training needs both classes (0 and 1) in label column.")

    if min(class_counts.values()) < 2:
        raise ValueError("Each label class needs at least 2 rows for stratified split.")

    x, y = split_features(df)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pos = max(1, int((y_train == 1).sum()))
    neg = max(1, int((y_train == 0).sum()))
    positive_weight = float(max(1.0, neg / pos))

    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=250,
        max_depth=5,
        learning_rate=0.05,
        subsample=1.0,
        colsample_bytree=1.0,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=1,
        scale_pos_weight=positive_weight,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    threshold = _threshold_for_target_recall(y_test, probabilities, target_recall=target_recall)
    threshold_predictions = (probabilities >= threshold).astype(int)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    shap_summary = _compute_shap_summary(model=model, x_reference=x_train)
    SHAP_PATH.write_text(json.dumps(shap_summary, indent=2), encoding="utf-8")

    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 6),
        "threshold": round(float(threshold), 6),
        "threshold_strategy": "recall_first",
        "target_recall": round(float(target_recall), 4),
        "rows_used": int(len(df)),
        "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
        "features": MODEL_FEATURES,
        "source_path": str(data_path),
        "model_type": "XGBoost",
        "deterministic": True,
    }
    METADATA_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Model saved to: {MODEL_PATH}")
    print(f"Metadata saved to: {METADATA_PATH}")
    print(f"SHAP summary saved to: {SHAP_PATH}")
    print("Classification report:")
    print(classification_report(y_test, threshold_predictions))
    print(f"ROC-AUC: {roc_auc_score(y_test, probabilities):.4f}")
    achieved_recall = float((threshold_predictions[y_test == 1].sum() / max(1, (y_test == 1).sum())))
    print(f"Selected threshold (target recall {target_recall:.2f}): {threshold:.4f}")
    print(f"Achieved recall at threshold: {achieved_recall:.4f}")


def _best_threshold(y_true: pd.Series, probabilities: pd.Series | list[float]) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    if len(thresholds) == 0:
        return 0.5

    f1_scores = []
    for idx in range(len(thresholds)):
        p = precision[idx]
        r = recall[idx]
        if (p + r) <= 0:
            f1_scores.append(0.0)
        else:
            f1_scores.append((2 * p * r) / (p + r))
    best_index = int(max(range(len(f1_scores)), key=lambda i: f1_scores[i]))
    return float(thresholds[best_index])


def _threshold_for_target_recall(
    y_true: pd.Series,
    probabilities: pd.Series | list[float],
    target_recall: float,
) -> float:
    bounded_target = min(0.99, max(0.01, float(target_recall)))
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)

    if len(thresholds) == 0:
        return 0.5

    for idx, threshold in enumerate(thresholds):
        if float(recall[idx]) >= bounded_target:
            return float(threshold)

    return _best_threshold(y_true, probabilities)


def _compute_shap_summary(model: XGBClassifier, x_reference: pd.DataFrame) -> dict:
    sample = x_reference.iloc[: min(1000, len(x_reference))]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)

    mean_abs = abs(pd.DataFrame(shap_values, columns=sample.columns)).mean().to_dict()
    sorted_features = sorted(mean_abs.items(), key=lambda item: item[1], reverse=True)
    top_features = [{"feature": name, "mean_abs_shap": round(float(value), 6)} for name, value in sorted_features]

    return {
        "method": "TreeExplainer",
        "rows_evaluated": int(len(sample)),
        "top_features": top_features,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train deterministic local AML model (XGBoost + SHAP).")
    parser.add_argument(
        "--data-path",
        default=str(DATA_PATH),
        help="Path to training CSV (unified or PaySim schema).",
    )
    parser.add_argument(
        "--target-recall",
        type=float,
        default=0.70,
        help="Recall target used for threshold selection (AML-oriented).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train_model(data_path=Path(args.data_path), target_recall=float(args.target_recall))
