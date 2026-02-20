from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict


@dataclass
class Weights:
    raw: float
    ml: float
    graph: float


class DynamicWeightManager:
    def __init__(self, raw: float, ml: float, graph: float) -> None:
        self._lock = Lock()
        self._weights = self._normalize({"raw": raw, "ml": ml, "graph": graph})

    def get_weights(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._weights)

    def recalibrate(self, feedback_label: str) -> Dict[str, float]:
        with self._lock:
            candidate = dict(self._weights)

            if feedback_label == "confirmed_fraud":
                candidate["graph"] += 0.05
                candidate["ml"] += 0.03
                candidate["raw"] -= 0.08
            elif feedback_label == "false_positive":
                candidate["raw"] += 0.08
                candidate["graph"] -= 0.05
                candidate["ml"] -= 0.03
            elif feedback_label == "needs_review":
                candidate["raw"] += 0.02
                candidate["graph"] += 0.01
                candidate["ml"] -= 0.03

            self._weights = self._normalize(candidate)
            return dict(self._weights)

    def set_weights(self, raw: float, ml: float, graph: float) -> Dict[str, float]:
        with self._lock:
            self._weights = self._normalize({"raw": raw, "ml": ml, "graph": graph})
            return dict(self._weights)

    @staticmethod
    def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
        clipped = {
            key: min(0.75, max(0.10, float(value)))
            for key, value in weights.items()
        }
        total = clipped["raw"] + clipped["ml"] + clipped["graph"]
        if total <= 0:
            return {"raw": 0.34, "ml": 0.33, "graph": 0.33}

        return {
            "raw": round(clipped["raw"] / total, 4),
            "ml": round(clipped["ml"] / total, 4),
            "graph": round(clipped["graph"] / total, 4),
        }
