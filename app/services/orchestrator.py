from __future__ import annotations

from uuid import uuid4

from app.schemas.scam_exposure import (
    AnalystDecision,
    FeedbackRequest,
    FeedbackResponse,
    LayerRiskBreakdown,
    OrchestrationStep,
    RiskWeights,
    ScamExposureRequest,
    ScamExposureResponse,
    WeightsResponse,
)
from app.services.case_store import CaseStore
from app.services.graph_service import evaluate_graph_risk
from app.services.ml_service import evaluate_ml_risk
from app.services.raw_service import evaluate_raw_risk
from app.services.risk_aggregator import aggregate_risk
from app.services.weight_manager import DynamicWeightManager


class RiskOrchestrator:
    def __init__(self) -> None:
        self._weights = DynamicWeightManager(raw=0.35, ml=0.30, graph=0.35)
        self._cases = CaseStore()

    def process(self, payload: ScamExposureRequest) -> ScamExposureResponse:
        trace = [
            OrchestrationStep(stage="ingest", status="completed", detail="Transaction payload accepted."),
        ]

        raw_result = evaluate_raw_risk(payload)
        trace.append(OrchestrationStep(stage="raw", status="completed", detail="Deterministic checks executed."))

        ml_result = evaluate_ml_risk(payload)
        trace.append(OrchestrationStep(stage="ml", status="completed", detail="Probabilistic proxy scoring executed."))

        graph_result = evaluate_graph_risk(payload.account_id)
        trace.append(OrchestrationStep(stage="graph", status="completed", detail="Graph intelligence signals computed."))

        active_weights = self._weights.get_weights()

        aggregated = aggregate_risk(
            raw_score=raw_result.score,
            ml_score=ml_result.score,
            graph_score=graph_result.score,
            weights=active_weights,
        )
        trace.append(OrchestrationStep(stage="aggregate", status="completed", detail="Layer scores merged into bounded final risk."))

        analyst_decision = self._analyst_gate(aggregated.exposure_level, raw_result.score)
        trace.append(
            OrchestrationStep(
                stage="analyst",
                status="queued" if analyst_decision.required else "skipped",
                detail=analyst_decision.reason,
            )
        )

        case_id = str(uuid4())
        self._cases.put(
            case_id,
            {
                "account_id": payload.account_id,
                "risk_score": aggregated.final_risk,
                "exposure_level": aggregated.exposure_level,
                "weights_used": active_weights,
                "raw_rule_contributions": raw_result.contributions,
            },
        )

        risk_breakdown = {
            "raw": LayerRiskBreakdown(
                score=raw_result.score,
                reasoning=raw_result.reasoning,
                contributions=raw_result.contributions,
            ),
            "ml": LayerRiskBreakdown(
                score=ml_result.score,
                reasoning=ml_result.reasoning,
                contributions=ml_result.contributions,
            ),
            "graph": LayerRiskBreakdown(
                score=graph_result.score,
                reasoning=graph_result.reasoning,
                contributions=graph_result.contributions,
            ),
        }

        summary = (
            f"Final risk {aggregated.final_risk}/100 based on RAW({raw_result.score}), "
            f"ML({ml_result.score}), and GRAPH({graph_result.score}) layers."
        )

        return ScamExposureResponse(
            case_id=case_id,
            account_id=payload.account_id,
            risk_score=aggregated.final_risk,
            trust_score=aggregated.trust_score,
            exposure_level=aggregated.exposure_level,
            risk_formula="Risk_final = w1*RAW + w2*ML + w3*GRAPH",
            weights_used=RiskWeights(
                raw=active_weights["raw"],
                ml=active_weights["ml"],
                graph=active_weights["graph"],
            ),
            risk_breakdown=risk_breakdown,
            orchestrator_trace=trace,
            analyst_decision=analyst_decision,
            summary=summary,
        )

    def apply_feedback(self, payload: FeedbackRequest) -> FeedbackResponse:
        if payload.outcome not in {"confirmed_fraud", "false_positive", "needs_review"}:
            return FeedbackResponse(
                case_id=payload.case_id,
                status="rejected",
                updated_weights=RiskWeights(**self._weights.get_weights()),
                message="Invalid outcome. Use confirmed_fraud, false_positive, or needs_review.",
            )

        case = self._cases.get(payload.case_id)
        if case is None:
            return FeedbackResponse(
                case_id=payload.case_id,
                status="not_found",
                updated_weights=RiskWeights(**self._weights.get_weights()),
                message="Case not found for feedback.",
            )

        updated_weights = self._weights.recalibrate(payload.outcome)
        self._cases.update(payload.case_id, {"feedback": payload.outcome, "notes": payload.notes})

        return FeedbackResponse(
            case_id=payload.case_id,
            status="updated",
            updated_weights=RiskWeights(**updated_weights),
            message="Weights recalibrated from analyst feedback.",
        )

    def get_weights(self) -> WeightsResponse:
        return WeightsResponse(weights=RiskWeights(**self._weights.get_weights()))

    def list_cases(self, limit: int = 200) -> list[dict]:
        return self._cases.list_recent(limit=limit)

    @staticmethod
    def _analyst_gate(exposure_level: str, raw_score: float) -> AnalystDecision:
        if exposure_level == "High" or raw_score >= 90.0:
            return AnalystDecision(required=True, reason="Escalated for human analyst review due to high-risk posture.")
        return AnalystDecision(required=False, reason="No escalation required; continue passive monitoring.")
