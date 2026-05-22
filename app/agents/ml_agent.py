from __future__ import annotations
import time
from typing import Dict, Any
from app.agents.framework import BaseAgent, AgentResult, EventBus
from app.services.ml_service import evaluate_ml_risk
from app.schemas.scam_exposure import ScamExposureRequest

class MLAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("MLAgent", event_bus)
        self.tools.register("predict_ml_risk", self.predict_ml_risk, "Run XGBoost ML prediction models.")

    def predict_ml_risk(self, payload: ScamExposureRequest) -> Dict[str, Any]:
        res = evaluate_ml_risk(payload)
        return {
            "score": res.score,
            "contributions": res.contributions,
            "reasoning": res.reasoning
        }

    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        start_time = time.perf_counter()
        
        payload = ScamExposureRequest(
            account_id=context.get("account_id", "unknown"),
            upi_id=context.get("upi_id"),
            transaction_amount=float(context.get("transaction_amount", 0.0)),
            tx_count_last_hour=int(context.get("tx_count_last_hour", 1)),
            transaction_note=context.get("transaction_note")
        )
        
        res = self.tools.invoke("predict_ml_risk", payload=payload)
        score = res["score"]
        contributions = res["contributions"]
        reasoning_list = res["reasoning"]
        
        # Decide action based on score threshold
        if score >= 75:
            decision = "BLOCK"
        elif score >= 45:
            decision = "ESCALATE"
        elif score >= 20:
            decision = "REVIEW"
        else:
            decision = "ALLOW"
            
        # Explanations from SHAP contributions
        shap_details = [f"{k}: {v:+}" for k, v in contributions.items() if abs(v) > 0.01]
        reasoning = (
            f"ML risk prediction model scored risk at {score}/100. "
            f"Top SHAP features driving prediction: {', '.join(shap_details) if shap_details else 'None'}. "
            f"Details: {'; '.join(reasoning_list)}"
        )
        
        execution_time = (time.perf_counter() - start_time) * 1000.0
        evidence = [{"type": "ml_shap_contribution", "feature": k, "impact": v} for k, v in contributions.items()]
        
        result = AgentResult(
            agent_name=self.name,
            score=score,
            confidence=0.92,  # ROC-AUC of the trained XGBoost model is 0.929
            decision=decision,
            reasoning=reasoning,
            evidence=evidence,
            tools_used=["predict_ml_risk"],
            execution_time_ms=execution_time,
            metadata={"contributions": contributions}
        )
        
        await self.send_message(
            receiver="OrchestratorAgent",
            msg_type="response",
            payload={"result": result.__dict__},
            correlation_id=correlation_id
        )
        
        return result
