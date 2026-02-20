from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    max_score: float = 100.0
    raw_weight: float = 0.35
    ml_weight: float = 0.30
    graph_weight: float = 0.35
    high_risk_threshold: float = 75.0
    medium_risk_threshold: float = 40.0
    velocity_threshold_per_hour: int = 5
    high_amount_threshold: float = 50_000.0


CONFIG = RiskConfig()
