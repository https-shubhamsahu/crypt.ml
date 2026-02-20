from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas.scam_exposure import (
    FeedbackRequest,
    FeedbackResponse,
    ScamExposureRequest,
    ScamExposureResponse,
    WeightsResponse,
)
from app.api.v1.security import require_api_key
from app.services.orchestrator import RiskOrchestrator

router = APIRouter(prefix="/api/v1", tags=["scam-exposure"])
orchestrator = RiskOrchestrator()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/scam-exposure", response_model=ScamExposureResponse)
def scam_exposure(
    payload: ScamExposureRequest,
    _: None = Depends(require_api_key),
) -> ScamExposureResponse:
    return orchestrator.process(payload)


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(
    payload: FeedbackRequest,
    _: None = Depends(require_api_key),
) -> FeedbackResponse:
    return orchestrator.apply_feedback(payload)


@router.get("/weights", response_model=WeightsResponse)
def get_weights(_: None = Depends(require_api_key)) -> WeightsResponse:
    return orchestrator.get_weights()
