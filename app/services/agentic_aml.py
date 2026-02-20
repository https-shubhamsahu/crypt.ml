from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Dict, List, Sequence
import uuid

import networkx as nx
import pandas as pd

from app.schemas.scam_exposure import ScamExposureRequest
from app.services.graph_service import evaluate_graph_risk
from app.services.ml_service import evaluate_ml_risk
from app.services.raw_service import evaluate_raw_risk


@dataclass
class RAWDecision:
    transaction_id: str
    action: str
    risk_score: float
    violations: List[str]


@dataclass
class SARDecision:
    transaction_id: str
    ml_score: float
    graph_score: float
    ensemble_score: float
    top_signals: Dict[str, float]


@dataclass
class AMLFinalDecision:
    transaction_id: str
    final_decision: str
    combined_risk_score: float
    reason: str
    raw_decision: RAWDecision
    sar_decision: SARDecision


class RAWAgent:
    def evaluate(self, transaction_id: str, payload: ScamExposureRequest) -> RAWDecision:
        raw = evaluate_raw_risk(payload)

        if raw.score >= 85:
            action = "BLOCK"
        elif raw.score >= 55:
            action = "ESCALATE"
        elif raw.score >= 25:
            action = "REVIEW"
        else:
            action = "ALLOW"

        return RAWDecision(
            transaction_id=transaction_id,
            action=action,
            risk_score=raw.score / 100.0,
            violations=raw.reasoning,
        )


class SARAgent:
    def evaluate(self, transaction_id: str, payload: ScamExposureRequest) -> SARDecision:
        ml = evaluate_ml_risk(payload)
        graph = evaluate_graph_risk(payload.account_id)

        ensemble = min(100.0, (0.6 * ml.score) + (0.4 * graph.score))

        signals = {
            "ml_probability": round(ml.score / 100.0, 4),
            "graph_proximity": round(graph.contributions.get("path_proximity", 0.0) / 100.0, 4),
            "graph_centrality": round(graph.contributions.get("centrality", 0.0) / 100.0, 4),
        }

        return SARDecision(
            transaction_id=transaction_id,
            ml_score=ml.score / 100.0,
            graph_score=graph.score / 100.0,
            ensemble_score=ensemble / 100.0,
            top_signals=signals,
        )


class A2AMessage:
    @staticmethod
    def request(agent: str, action: str, payload: Dict) -> Dict:
        return {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": agent,
            "action": action,
            "payload": payload,
        }

    @staticmethod
    def response(success: bool, payload: Dict) -> Dict:
        return {
            "success": success,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }


class AMLOrchestratorA2A:
    def __init__(self) -> None:
        self.raw_agent = RAWAgent()
        self.sar_agent = SARAgent()

    def process(self, transaction: Dict) -> AMLFinalDecision:
        transaction_id = str(transaction.get("transaction_id", f"TXN_{uuid.uuid4().hex[:10]}"))
        payload = ScamExposureRequest(
            account_id=str(transaction.get("src_account", transaction.get("account_id", "acct_unknown"))),
            upi_id=transaction.get("upi_id"),
            transaction_amount=float(transaction.get("amount", transaction.get("transaction_amount", 0.0))),
            tx_count_last_hour=int(transaction.get("tx_count_last_hour", 1)),
            transaction_note=transaction.get("transaction_note"),
        )

        raw_request = A2AMessage.request(agent="RAW", action="evaluate", payload={"transaction_id": transaction_id})
        _ = raw_request
        raw = self.raw_agent.evaluate(transaction_id, payload)

        sar_request = A2AMessage.request(agent="SAR", action="evaluate", payload={"transaction_id": transaction_id})
        _ = sar_request
        sar = self.sar_agent.evaluate(transaction_id, payload)

        final_decision, reason = self._combine(raw, sar)

        return AMLFinalDecision(
            transaction_id=transaction_id,
            final_decision=final_decision,
            combined_risk_score=round((0.55 * raw.risk_score + 0.45 * sar.ensemble_score), 4),
            reason=reason,
            raw_decision=raw,
            sar_decision=sar,
        )

    @staticmethod
    def _combine(raw: RAWDecision, sar: SARDecision) -> tuple[str, str]:
        if raw.action == "BLOCK":
            return "BLOCK", "RAW hard-rule triggered block."
        if raw.action in {"ESCALATE", "REVIEW"} or sar.ensemble_score >= 0.7:
            return "ESCALATE", "High composite risk from RAW/SAR agents."
        if sar.ensemble_score >= 0.5:
            return "REVIEW", "Moderate SAR ensemble risk."
        return "ALLOW", "No severe risk indicators detected."


class SARReportGenerator:
    @staticmethod
    def build_report(final_decision: AMLFinalDecision, transaction: Dict) -> Dict:
        return {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now(UTC).isoformat(),
            "transaction": {
                "transaction_id": final_decision.transaction_id,
                "amount": float(transaction.get("amount", transaction.get("transaction_amount", 0.0))),
                "source": transaction.get("src_account", transaction.get("account_id", "unknown")),
                "destination": transaction.get("dst_account", "unknown"),
                "channel": transaction.get("channel", "unknown"),
                "country": transaction.get("country", "unknown"),
            },
            "final_decision": {
                "action": final_decision.final_decision,
                "combined_risk_score": final_decision.combined_risk_score,
                "reason": final_decision.reason,
            },
            "raw_agent": asdict(final_decision.raw_decision),
            "sar_agent": asdict(final_decision.sar_decision),
        }


def batch_metrics(results: Sequence[AMLFinalDecision]) -> Dict:
    if not results:
        return {"total": 0, "decision_counts": {}, "mean_risk": 0.0}

    counts: Dict[str, int] = {}
    scores: List[float] = []

    for result in results:
        counts[result.final_decision] = counts.get(result.final_decision, 0) + 1
        scores.append(result.combined_risk_score)

    return {
        "total": len(results),
        "decision_counts": counts,
        "mean_risk": round(sum(scores) / len(scores), 4),
    }


def build_graph_from_transactions(df: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    if "src_account" not in df.columns or "dst_account" not in df.columns:
        return graph

    for _, row in df.iterrows():
        src = str(row.get("src_account"))
        dst = str(row.get("dst_account"))
        weight = float(row.get("amount", 1.0))
        if graph.has_edge(src, dst):
            graph[src][dst]["weight"] += weight
        else:
            graph.add_edge(src, dst, weight=weight)
    return graph
