from __future__ import annotations
import time
from typing import Dict, Any
from app.agents.framework import BaseAgent, AgentResult, EventBus
from app.services.nlp_service import analyze_note_risk, _is_llm_enabled

class NLPAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("NLPAgent", event_bus)
        self.tools.register("analyze_narrative_risk", self.analyze_narrative_risk, "Compute NLP narrative risk scoring via lexicon + LLM.")

    def analyze_narrative_risk(self, note: str) -> Dict[str, Any]:
        # Clean note to avoid crash
        note = str(note or "").strip()
        if not note:
            return {"score": 0.0, "matched_terms": [], "llm_summary": "No note provided.", "llm_enabled": False}
        res = analyze_note_risk(note)
        return {
            "score": res.score,
            "matched_terms": res.matched_terms,
            "llm_summary": res.llm_summary,
            "llm_enabled": _is_llm_enabled()
        }

    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        start_time = time.perf_counter()
        
        note = context.get("transaction_note", "")
        
        res = self.tools.invoke("analyze_narrative_risk", note=note)
        score = res["score"]
        matched_terms = res["matched_terms"]
        llm_summary = res["llm_summary"]
        
        if score >= 75:
            decision = "BLOCK"
        elif score >= 45:
            decision = "ESCALATE"
        elif score >= 20:
            decision = "REVIEW"
        else:
            decision = "ALLOW"
            
        reasoning = (
            f"NLP Narrative risk evaluated at {score}/100. "
            f"Matched risk lexicon terms: {', '.join(matched_terms) if matched_terms else 'None'}. "
            f"AI Assessment Summary: {llm_summary}"
        )
        
        execution_time = (time.perf_counter() - start_time) * 1000.0
        evidence = [{"type": "nlp_risk_term", "term": t} for t in matched_terms]
        if llm_summary:
            evidence.append({"type": "ai_nlp_assessment", "summary": llm_summary})
            
        result = AgentResult(
            agent_name=self.name,
            score=score,
            confidence=0.80,
            decision=decision,
            reasoning=reasoning,
            evidence=evidence,
            tools_used=["analyze_narrative_risk"],
            execution_time_ms=execution_time,
            metadata={"matched_terms": matched_terms, "llm_enabled": res["llm_enabled"]}
        )
        
        await self.send_message(
            receiver="OrchestratorAgent",
            msg_type="response",
            payload={"result": result.__dict__},
            correlation_id=correlation_id
        )
        
        return result
