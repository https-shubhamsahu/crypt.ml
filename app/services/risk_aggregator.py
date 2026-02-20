from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.core.config import CONFIG


@dataclass
class AggregatedRiskResult:
    final_risk: float
    trust_score: float
    exposure_level: str


def aggregate_risk(
    raw_score: float,
    ml_score: float,
    graph_score: float,
    weights: Mapping[str, float] | None = None,
) -> AggregatedRiskResult:
    active_weights = weights or {
        "raw": CONFIG.raw_weight,
        "ml": CONFIG.ml_weight,
        "graph": CONFIG.graph_weight,
    }

    final = (
        active_weights["raw"] * raw_score
        + active_weights["ml"] * ml_score
        + active_weights["graph"] * graph_score
    )
    bounded_final = round(max(0.0, min(CONFIG.max_score, final)), 2)

    trust_score = round(max(1.0, 10.0 - (bounded_final / 10.0)), 2)

    if bounded_final >= CONFIG.high_risk_threshold:
        exposure = "High"
    elif bounded_final >= CONFIG.medium_risk_threshold:
        exposure = "Medium"
    else:
        exposure = "Low"

    return AggregatedRiskResult(
        final_risk=bounded_final,
        trust_score=trust_score,
        exposure_level=exposure,
    )
