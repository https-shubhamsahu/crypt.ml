from __future__ import annotations
import time
from typing import Dict, Any
from app.agents.framework import BaseAgent, AgentResult, EventBus
from app.services.raw_service import evaluate_raw_risk
from app.schemas.scam_exposure import ScamExposureRequest

class RAWAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("RAWAgent", event_bus)
        self.tools.register("evaluate_rules", self.evaluate_rules, "Evaluate RAW deterministic rules on the payload.")

    def evaluate_rules(self, payload: ScamExposureRequest) -> Dict[str, Any]:
        res = evaluate_raw_risk(payload)
        return {
            "score": res.score,
            "reasoning": res.reasoning,
            "rules_triggered": len(res.reasoning)
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
        
        # Invoke tool
        res = self.tools.invoke("evaluate_rules", payload=payload)
        score = res["score"]
        reasoning_list = res["reasoning"]
        
        if score >= 85:
            decision = "BLOCK"
        elif score >= 55:
            decision = "ESCALATE"
        elif score >= 25:
            decision = "REVIEW"
        else:
            decision = "ALLOW"
            
        reasoning = (
            f"RAW compliance score is {score}/100. "
            f"Triggered {res['rules_triggered']} deterministic rules: "
            + ("; ".join(reasoning_list) if reasoning_list else "No violations detected.")
        )
        
        execution_time = (time.perf_counter() - start_time) * 1000.0
        
        # Support dynamic observations
        evidence = [{"type": "rule_violation", "description": r} for r in reasoning_list]
        
        result = AgentResult(
            agent_name=self.name,
            score=score,
            confidence=1.0,  # Deterministic has absolute confidence
            decision=decision,
            reasoning=reasoning,
            evidence=evidence,
            tools_used=["evaluate_rules"],
            execution_time_ms=execution_time
        )
        
        # Publish message if event bus exists
        await self.send_message(
            receiver="OrchestratorAgent",
            msg_type="response",
            payload={"result": result.__dict__},
            correlation_id=correlation_id
        )
        
        return result
