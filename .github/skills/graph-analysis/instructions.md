# GraphRiskSkill

Use this skill when a task involves **graph-based AML risk analysis**.

## Auto-match signals
Load this skill when the prompt mentions any of:
- shortest path to risky/sanctioned/flagged nodes
- centrality-based influence/risk propagation
- trust score / trust rank / exposure score
- graph intelligence layer for AML or scam exposure

## What this skill provides
- Deterministic shortest-path risk signal
- Centrality-derived influence signal
- Trust-rank style propagation from known risky seeds
- Explainable, bounded graph score components

## Files
- `sample_scripts.py`: reusable functions for path, centrality, and trust rank
- `examples/graph_risk_example.py`: compact usage example

## Integration notes
- Keep graph outputs normalized and explainable.
- Return intermediate components (path, centrality, trust rank) for auditability.
- Keep final score bounding in the calling risk-aggregation layer.
- For hackathon MVP, prefer local NetworkX workflows over remote infrastructure.

## MCP boundary
- Use MCP only when the task specifically needs:
	- database access
	- PaySim querying
	- live Neo4j graph queries
	- GitHub issue tracking integration
- Otherwise keep analysis local to reduce context/tooling overhead.

## Local quick start
- Install dependencies: `pip install -r requirements.txt`
- Run demo example: `python .github/skills/graph-analysis/examples/graph_risk_example.py`
