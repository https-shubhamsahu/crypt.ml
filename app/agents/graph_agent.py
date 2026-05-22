from __future__ import annotations
import time
from typing import Dict, Any
from app.agents.framework import BaseAgent, AgentResult, EventBus
from app.services.graph_service import evaluate_graph_risk, get_current_graph, find_hub_nodes

class GraphAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("GraphAgent", event_bus)
        self.tools.register("evaluate_network_risk", self.evaluate_network_risk, "Compute shortest paths, centrality, and TrustRank on network graphs.")
        self.tools.register("detect_hubs", self.detect_hubs, "Identify high-degree hub nodes in the graph.")

    def evaluate_network_risk(self, account_id: str) -> Dict[str, Any]:
        res = evaluate_graph_risk(account_id)
        return {
            "score": res.score,
            "reasoning": res.reasoning,
            "contributions": res.contributions
        }

    def detect_hubs(self, threshold: int = 5) -> Dict[str, Any]:
        graph = get_current_graph()
        hubs = find_hub_nodes(graph, threshold)
        return {"hubs": hubs}

    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        start_time = time.perf_counter()
        
        account_id = context.get("account_id", "unknown")
        
        # Evaluate graph
        res = self.tools.invoke("evaluate_network_risk", account_id=account_id)
        score = res["score"]
        contributions = res["contributions"]
        reasoning_list = res["reasoning"]
        
        if score >= 75:
            decision = "BLOCK"
        elif score >= 45:
            decision = "ESCALATE"
        elif score >= 20:
            decision = "REVIEW"
        else:
            decision = "ALLOW"
            
        reasoning = (
            f"Graph network risk evaluated at {score}/100. "
            f"Analysis findings: {'; '.join(reasoning_list)}"
        )
        
        execution_time = (time.perf_counter() - start_time) * 1000.0
        evidence = [{"type": "graph_signal", "signal": k, "score": v} for k, v in contributions.items()]
        
        result = AgentResult(
            agent_name=self.name,
            score=score,
            confidence=0.85,
            decision=decision,
            reasoning=reasoning,
            evidence=evidence,
            tools_used=["evaluate_network_risk"],
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
