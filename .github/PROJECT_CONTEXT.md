# crypt.ml — Project Context

## 1. Project Overview

crypt.ml is a next-generation Anti-Money Laundering (AML) system designed to solve the Compliance Trilemma:

1. High Recall — Detect complex multi-hop laundering networks (mule rings, layering).
2. Low False Positives — Reduce noise that overwhelms compliance teams.
3. Explainability — Provide transparent, regulator-friendly reasoning.

The system replaces static rule engines with a multi-layer, agentic architecture that combines deterministic logic, machine learning, and graph intelligence.

---

## 2. Core Architecture

crypt.ml is built on a 3-layer intelligence model.

### Layer 1 — RAW Agent (Deterministic Guardrails)

Purpose:
Immediate regulatory enforcement.

Examples:
- Sanctioned entity checks
- Velocity rules (e.g. > 5 transactions/hour)
- Fixed reporting thresholds
- Regex-based compliance filters

Characteristics:
- Zero tolerance
- Binary decisions
- Low computational cost

---

### Layer 2 — SAR Agent (Probabilistic ML)

Model:
- XGBoost (primary)
- Outputs probability score (P_risk)

Feature Engineering:
- Temporal entropy (transaction time irregularity)
- Z-score deviation from historical mean
- Account age vs transaction velocity ratio
- Behavioral anomalies

Explainability:
- SHAP values for feature-level transparency

Output:
- ML risk score (0–100 normalized)
- Feature contribution explanation

---

### Layer 3 — Graph Intelligence (Relational Analysis)

Purpose:
Detect structural laundering behavior that tabular ML cannot see.

Graph Model:
- Nodes: Accounts / UPI IDs
- Edges: Transactions (directed, weighted)

Metrics Used:
- Shortest path to known bad actors
- Community detection (mule clusters)
- Eigenvector centrality (influence inside cluster)
- PageRank / TrustRank proximity

Graph Engine:
- NetworkX (MVP, in-memory)
- Neo4j (scalable version)

Output:
- Graph risk score (0–100 normalized)
- Structural explanation

---

## 3. Risk Aggregation Formula

Final risk is dynamically weighted:

Risk_final = w1 * RAW + w2 * ML + w3 * GRAPH

Where:
- w1, w2, w3 are dynamically adjustable weights
- Scores are normalized to 0–100
- Explainability must be preserved

Weights can be recalibrated based on human feedback.

---

## 4. Agentic Orchestrator

The system is structured as a stateful workflow (LangGraph-style).

Flow:
1. Transaction ingested
2. Pass through Layer 1
3. Pass through Layer 2
4. Pass through Layer 3
5. Aggregate risk
6. If threshold exceeded → trigger Analyst Agent
7. Generate narrative explanation
8. Human feedback stored
9. Dynamic weight adjustment applied

System must support Human-in-the-Loop reinforcement.

---

## 5. Consumer Feature — Scam Exposure Scanner

A B2C extension of Graph Intelligence.

Input:
- UPI ID
- Bank account number
- Suspicious transaction reference

Logic:
- Compute shortest path to flagged nodes
- Evaluate cluster membership
- Measure centrality influence
- Aggregate structural exposure

Output:
- Risk Score (0–100)
- Trust Score (1–10)
- Exposure Level (Low / Medium / High)
- Plain English explanation

Goal:
Prevent scams before funds leave the user’s account.

---

## 6. Tech Stack

Backend:
- FastAPI
- Pydantic models
- Modular service architecture

Graph:
- NetworkX (MVP)
- Neo4j (future)

ML:
- XGBoost
- SHAP
- Scikit-learn utilities

Orchestration:
- LangGraph (stateful workflow)
- SQLite / PostgreSQL for persistence

Frontend:
- Streamlit (admin)
- React (consumer, future)

Dataset:
- PaySim (synthetic AML dataset)

---

## 7. Development Principles

When generating code:

- Use modular architecture
- Separate API layer from business logic
- Keep risk calculations isolated in service modules
- Always include type hints
- Avoid magic numbers
- Normalize risk scores
- Maintain explainability
- Build MVP first, scale later

Avoid:
- Monolithic files
- Hardcoded risk values without explanation
- Unbounded risk scoring
- Overengineering for hackathon version

---

## 8. Current MVP Goal

Build a working Scam Exposure Scanner that:

1. Accepts account ID
2. Queries graph
3. Computes proximity risk
4. Returns JSON response with explanation
5. Can be demoed clearly

Focus on:
- Functionality
- Clean architecture
- Strong demo narrative
- Fast iteration
