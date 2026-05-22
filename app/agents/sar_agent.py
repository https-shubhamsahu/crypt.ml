from __future__ import annotations
import time
from typing import Dict, Any, List
from app.agents.framework import BaseAgent, AgentResult, EventBus
from app.services.agentic_aml import SARReportGenerator, AMLFinalDecision, RAWDecision, SARDecision

class SARAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("SARAgent", event_bus)
        self.tools.register("draft_regulatory_sar", self.draft_regulatory_sar, "Compile formal Suspicious Activity Report (SAR) template.")

    def draft_regulatory_sar(self, context: Dict[str, Any], final_decision: Dict[str, Any]) -> Dict[str, Any]:
        # Wrap into the format expected by SARReportGenerator
        raw_dec = RAWDecision(
            transaction_id=final_decision.get("transaction_id", "unknown"),
            action=final_decision.get("raw_action", "REVIEW"),
            risk_score=final_decision.get("raw_score", 0.0) / 100.0,
            violations=final_decision.get("raw_violations", [])
        )
        sar_dec = SARDecision(
            transaction_id=final_decision.get("transaction_id", "unknown"),
            ml_score=final_decision.get("ml_score", 0.0) / 100.0,
            graph_score=final_decision.get("graph_score", 0.0) / 100.0,
            ensemble_score=final_decision.get("ensemble_score", 0.0) / 100.0,
            top_signals=final_decision.get("top_signals", {})
        )
        final_dec_obj = AMLFinalDecision(
            transaction_id=final_decision.get("transaction_id", "unknown"),
            final_decision=final_decision.get("final_decision", "REVIEW"),
            combined_risk_score=final_decision.get("combined_risk_score", 0.0) / 100.0,
            reason=final_decision.get("reason", ""),
            raw_decision=raw_dec,
            sar_decision=sar_dec
        )
        return SARReportGenerator.build_report(final_dec_obj, context)

    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        start_time = time.perf_counter()
        
        final_decision = context.get("final_decision_summary", {})
        transaction_details = context.get("transaction_details", {})
        
        res = self.tools.invoke("draft_regulatory_sar", context=transaction_details, final_decision=final_decision)
        
        score = final_decision.get("combined_risk_score", 0.0)
        decision = final_decision.get("final_decision", "REVIEW")
        
        reasoning = (
            f"SAR compliance agent compiled formal Suspicious Activity Report evidence. "
            f"Filing Urgency Score: {score}/100. "
            f"Filing action recommended: {decision}. "
            f"Case overview: {final_decision.get('reason', 'No primary flags.')}"
        )
        
        execution_time = (time.perf_counter() - start_time) * 1000.0
        evidence = [{"type": "compiled_sar_artifact", "report_id": res.get("report_id"), "urgency": score}]
        
        result = AgentResult(
            agent_name=self.name,
            score=score,
            confidence=1.0,
            decision=decision,
            reasoning=reasoning,
            evidence=evidence,
            tools_used=["draft_regulatory_sar"],
            execution_time_ms=execution_time,
            metadata={"sar_report": res}
        )
        
        await self.send_message(
            receiver="OrchestratorAgent",
            msg_type="response",
            payload={"result": result.__dict__},
            correlation_id=correlation_id
        )
        
        return result
