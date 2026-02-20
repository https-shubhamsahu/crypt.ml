from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ScamExposureRequest(BaseModel):
    account_id: str = Field(..., description="Customer account identifier")
    upi_id: Optional[str] = Field(default=None, description="Optional UPI identifier")
    transaction_amount: float = Field(ge=0.0, description="Current transaction amount")
    tx_count_last_hour: int = Field(ge=0, description="Recent velocity signal")
    transaction_note: Optional[str] = Field(default=None, description="Optional free-text context for NLP risk cues")


class LayerRiskBreakdown(BaseModel):
    score: float
    reasoning: List[str]
    contributions: Dict[str, float] = Field(default_factory=dict)


class OrchestrationStep(BaseModel):
    stage: str
    status: str
    detail: str


class AnalystDecision(BaseModel):
    required: bool
    reason: str


class RiskWeights(BaseModel):
    raw: float
    ml: float
    graph: float


class ScamExposureResponse(BaseModel):
    case_id: str
    account_id: str
    risk_score: float
    trust_score: float
    exposure_level: str
    risk_formula: str
    weights_used: RiskWeights
    risk_breakdown: Dict[str, LayerRiskBreakdown]
    orchestrator_trace: List[OrchestrationStep]
    analyst_decision: AnalystDecision
    summary: str


class FeedbackRequest(BaseModel):
    case_id: str
    outcome: str = Field(
        ...,
        description="One of confirmed_fraud, false_positive, needs_review",
    )
    notes: Optional[str] = None


class FeedbackResponse(BaseModel):
    case_id: str
    status: str
    updated_weights: RiskWeights
    message: str


class WeightsResponse(BaseModel):
    weights: RiskWeights
