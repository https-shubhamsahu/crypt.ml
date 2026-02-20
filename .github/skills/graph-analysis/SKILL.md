---
name: graph-analysis
description: GraphRiskSkill for AML/scam graph analysis (shortest path, centrality, trust-rank) with explainable risk signals and low-context loading.
---

# GraphRiskSkill

Use this skill when tasks mention graph-based fraud/AML analysis, exposure scoring, or relational risk.

## When to load
Load on prompts that include keywords like:
- shortest path to flagged/risky/sanctioned entities
- centrality, influence, mule ring clusters, community detection
- trust rank / propagation / exposure score
- graph intelligence layer, scam exposure scanner

## What it provides
- Shortest-path risk primitive: `shortest_path_distance_to_flagged`
- Centrality primitive: `normalized_eigenvector_centrality`
- Trust propagation primitive: `trust_rank`

## File map
- Core logic: `.github/skills/graph-analysis/sample_scripts.py`
- Usage example: `.github/skills/graph-analysis/examples/graph_risk_example.py`
- Additional guidance: `.github/skills/graph-analysis/instructions.md`

## Output style expectations
- Prefer bounded and explainable sub-scores over opaque single scores.
- Return intermediate graph components (path distance, centrality, trust rank) for auditability.
- Keep final 0-100 aggregation in the calling risk engine (`w1*RAW + w2*ML + w3*GRAPH`).

## MCP policy (Hackathon MVP)
- Keep this skill local by default.
- Use MCP only when required for database access, PaySim querying, live Neo4j graph queries, or GitHub issue tracking integration.