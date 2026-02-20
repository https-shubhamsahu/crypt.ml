from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import joblib
import pandas as pd

from app.core.config import CONFIG
from app.schemas.scam_exposure import ScamExposureRequest
from app.services.nlp_service import analyze_note_risk


MODEL_PATH = Path("artifacts/ml_model.joblib")


@dataclass
class MLRiskResult:
    score: float
    reasoning: List[str]
    contributions: Dict[str, float]


def evaluate_ml_risk(payload: ScamExposureRequest) -> MLRiskResult:
    nlp_result = analyze_note_risk(payload.transaction_note)
    model = _load_model()

    if model is not None:
        features = pd.DataFrame(
            [
                {
                    "transaction_amount": float(payload.transaction_amount),
                    "tx_count_last_hour": float(payload.tx_count_last_hour),
                    "has_upi": float(0 if payload.upi_id is None else 1),
                    "nlp_signal": float(nlp_result.score),
                }
            ]
        )
        probability = float(model.predict_proba(features)[0][1])
        score = round(probability * CONFIG.max_score, 2)

        contributions = {
            "transaction_amount": round(min(payload.transaction_amount / 150_000.0, 1.0) * 35.0, 2),
            "velocity_signal": round(min(payload.tx_count_last_hour / 12.0, 1.0) * 35.0, 2),
            "nlp_signal": round(min(nlp_result.score / 100.0, 1.0) * 20.0, 2),
            "account_presence": round((1.0 if payload.upi_id else 0.3) * 10.0, 2),
        }

        reasons = [
            "ML score generated from trained model artifact (artifacts/ml_model.joblib).",
            "NLP note signal (lexicon + optional local LLM) included as a model feature.",
        ]
        if nlp_result.matched_terms:
            reasons.append(f"NLP terms matched: {', '.join(nlp_result.matched_terms)}")
        if nlp_result.llm_summary:
            reasons.append(f"LLM summary: {nlp_result.llm_summary}")

        return MLRiskResult(score=score, reasoning=reasons, contributions=contributions)

    velocity_component = min(payload.tx_count_last_hour / 10.0, 1.0)
    amount_component = min(payload.transaction_amount / 100_000.0, 1.0)
    account_novelty_component = 0.35 if payload.upi_id is None else 0.1
    nlp_component = min(nlp_result.score / 100.0, 1.0)

    weighted_probability = (
        0.35 * velocity_component
        + 0.35 * amount_component
        + 0.15 * account_novelty_component
        + 0.15 * nlp_component
    )
    score = round(weighted_probability * CONFIG.max_score, 2)

    contributions = {
        "velocity_signal": round(velocity_component * 35.0, 2),
        "amount_signal": round(amount_component * 35.0, 2),
        "novelty_signal": round(account_novelty_component * 15.0, 2),
        "nlp_signal": round(nlp_component * 15.0, 2),
    }

    reasons = [
        "ML proxy score computed from velocity, amount, novelty, and NLP signals.",
        "No trained model artifact found; using deterministic proxy fallback.",
        "Contributions are exposed for regulator-friendly explainability.",
    ]
    if nlp_result.matched_terms:
        reasons.append(f"NLP terms matched: {', '.join(nlp_result.matched_terms)}")
    if nlp_result.llm_summary:
        reasons.append(f"LLM summary: {nlp_result.llm_summary}")

    return MLRiskResult(score=score, reasoning=reasons, contributions=contributions)


@lru_cache(maxsize=1)
def _load_model():
    if not MODEL_PATH.exists():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None
