from __future__ import annotations
import time
import uuid
from datetime import datetime, UTC
from typing import Dict, Any, List
from app.agents.framework import BaseAgent, AgentResult, EventBus, AgentMessage
from app.agents.raw_agent import RAWAgent
from app.agents.ml_agent import MLAgent
from app.agents.graph_agent import GraphAgent
from app.agents.nlp_agent import NLPAgent
from app.agents.sar_agent import SARAgent
from app.core import database
from app.services.graph_service import add_transaction_to_graph

class OrchestratorAgent(BaseAgent):
    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__("OrchestratorAgent", event_bus)
        
        # Instantiate sub-agents
        self.raw_agent = RAWAgent(event_bus)
        self.ml_agent = MLAgent(event_bus)
        self.graph_agent = GraphAgent(event_bus)
        self.nlp_agent = NLPAgent(event_bus)
        self.sar_agent = SARAgent(event_bus)
        
        # Subscribe to responses if event_bus is provided
        if self.event_bus:
            self.event_bus.subscribe("OrchestratorAgent", self.handle_agent_message)

        self.messages_log: List[Dict[str, Any]] = []

    async def handle_agent_message(self, message: AgentMessage) -> None:
        """Captures messages exchanged during execution for audit logging and UI display."""
        self.messages_log.append({
            "id": message.id,
            "sender": message.sender,
            "receiver": message.receiver,
            "msg_type": message.msg_type,
            "payload": message.payload,
            "timestamp": message.timestamp,
            "correlation_id": message.correlation_id
        })

    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        """Runs the fully asynchronous multi-agent coordination pipeline."""
        start_time = time.perf_counter()
        run_id = correlation_id or str(uuid.uuid4())
        self.messages_log.clear()
        
        timeline: List[Dict[str, Any]] = []
        
        # 1. Start Orchestration
        timeline.append({"stage": "Start", "agent": "OrchestratorAgent", "start_time": time.perf_counter() - start_time})
        await self.send_message(receiver="*", msg_type="broadcast", payload={"status": "Starting analysis", "run_id": run_id}, correlation_id=run_id)
        
        # Add to dynamic graph
        src = context.get("account_id", "unknown")
        dst = context.get("upi_id", "unknown")
        amt = float(context.get("transaction_amount", 1.0))
        add_transaction_to_graph(src, dst, amt)

        # 2. Trigger RAW Agent & NLP Agent in Parallel (first tier checks)
        raw_start = time.perf_counter() - start_time
        timeline.append({"stage": "RAW Compliance Analysis", "agent": "RAWAgent", "start_time": raw_start})
        raw_task = self.raw_agent.analyze(context, correlation_id=run_id)
        
        nlp_start = time.perf_counter() - start_time
        timeline.append({"stage": "NLP Narrative Risk Analysis", "agent": "NLPAgent", "start_time": nlp_start})
        nlp_task = self.nlp_agent.analyze(context, correlation_id=run_id)
        
        # Wait for first tier to complete
        import asyncio
        raw_res, nlp_res = await asyncio.gather(raw_task, nlp_task)
        
        timeline[-2]["end_time"] = time.perf_counter() - start_time
        timeline[-1]["end_time"] = time.perf_counter() - start_time

        # 3. Trigger ML Agent & Graph Agent in Parallel (second tier scoring)
        ml_start = time.perf_counter() - start_time
        timeline.append({"stage": "ML Prediction Scoring", "agent": "MLAgent", "start_time": ml_start})
        ml_task = self.ml_agent.analyze(context, correlation_id=run_id)
        
        graph_start = time.perf_counter() - start_time
        timeline.append({"stage": "Graph Structural Analysis", "agent": "GraphAgent", "start_time": graph_start})
        graph_task = self.graph_agent.analyze(context, correlation_id=run_id)
        
        ml_res, graph_res = await asyncio.gather(ml_task, graph_task)
        
        timeline[-2]["end_time"] = time.perf_counter() - start_time
        timeline[-1]["end_time"] = time.perf_counter() - start_time

        # 4. Synthesize Combined Final Score
        # Dynamic Weights (RAW = 0.35, ML = 0.30, Graph = 0.35)
        raw_w, ml_w, graph_w = 0.35, 0.30, 0.35
        combined_score = round((raw_w * raw_res.score) + (ml_w * ml_res.score) + (graph_w * graph_res.score), 2)
        
        # Decide final action
        if raw_res.decision == "BLOCK" or ml_res.decision == "BLOCK" or graph_res.decision == "BLOCK":
            final_decision = "BLOCK"
            reason = "CRITICAL: Blocked by deterministic RAW rules or severe machine learning / graph structural flags."
        elif combined_score >= 60.0 or raw_res.decision == "ESCALATE":
            final_decision = "ESCALATE"
            reason = "High composite transaction risk score or escalation from compliance agents."
        elif combined_score >= 30.0:
            final_decision = "REVIEW"
            reason = "Moderate risk scored by ML and network graph analyzers. Recommended for analyst review."
        else:
            final_decision = "ALLOW"
            reason = "Composite transaction risk falls well within standard acceptable bounds."

        # Include NLP flags if severe
        if nlp_res.score >= 70:
            final_decision = "ESCALATE"
            reason += f" Narrative analysis flagged critical risks: {nlp_res.reasoning}"

        # 5. Trigger SAR Agent (regulatory compilation)
        sar_start = time.perf_counter() - start_time
        timeline.append({"stage": "SAR Evidence Compilation", "agent": "SARAgent", "start_time": sar_start})
        
        final_decision_summary = {
            "transaction_id": context.get("transaction_id", f"TXN_{uuid.uuid4().hex[:10]}"),
            "raw_action": raw_res.decision,
            "raw_score": raw_res.score,
            "raw_violations": [e["description"] for e in raw_res.evidence],
            "ml_score": ml_res.score,
            "graph_score": graph_res.score,
            "ensemble_score": (ml_res.score * 0.6) + (graph_res.score * 0.4),
            "top_signals": {
                "ml_prob": ml_res.score / 100.0,
                "graph_proximity": graph_res.score / 100.0
            },
            "combined_risk_score": combined_score,
            "final_decision": final_decision,
            "reason": reason
        }
        
        sar_context = {
            "transaction_details": context,
            "final_decision_summary": final_decision_summary
        }
        
        sar_res = await self.sar_agent.analyze(sar_context, correlation_id=run_id)
        timeline[-1]["end_time"] = time.perf_counter() - start_time

        # End Orchestration
        timeline.append({"stage": "End", "agent": "OrchestratorAgent", "start_time": time.perf_counter() - start_time})
        timeline[-1]["end_time"] = time.perf_counter() - start_time
        
        execution_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Save to SQLite Database
        agent_results_list = [
            raw_res.__dict__,
            nlp_res.__dict__,
            ml_res.__dict__,
            graph_res.__dict__,
            sar_res.__dict__
        ]
        
        run_record = {
            "id": run_id,
            "transaction_id": final_decision_summary["transaction_id"],
            "account_id": context.get("account_id", "unknown"),
            "amount": amt,
            "final_score": combined_score,
            "final_decision": final_decision,
            "reasoning": reason,
            "agent_results": agent_results_list,
            "timeline": timeline,
            "messages": self.messages_log
        }
        
        # Save orchestration run and individual agent decisions
        database.insert_orchestration_run(run_record)
        for agent_res in agent_results_list:
            agent_res["run_id"] = run_id
            database.insert_agent_decision(agent_res)
            
        # File compliance case automatically if escalated
        if final_decision in ["BLOCK", "ESCALATE", "REVIEW"]:
            case_data = {
                "id": run_id,
                "account_id": context.get("account_id", "unknown"),
                "combined_risk_score": combined_score,
                "exposure_level": "High" if combined_score >= 70 else ("Medium" if combined_score >= 40 else "Low"),
                "final_decision": final_decision,
                "status": "OPEN",
                "details": run_record
            }
            database.insert_case(case_data)
            
        result = AgentResult(
            agent_name=self.name,
            score=combined_score,
            confidence=0.95,
            decision=final_decision,
            reasoning=reason,
            evidence=[{"type": "orchestrated_agents_run", "run_id": run_id}],
            tools_used=["coalesce_results"],
            execution_time_ms=execution_time_ms,
            metadata={
                "run_id": run_id,
                "timeline": timeline,
                "messages": self.messages_log,
                "agent_results": {ar["agent_name"]: ar for ar in agent_results_list}
            }
        )
        
        return result
