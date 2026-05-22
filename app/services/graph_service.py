from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
import networkx as nx
import pandas as pd
from app.core.config import CONFIG

FLAGGED_NODES: Set[str] = {"fraud_hub_1", "fraud_hub_2"}

# In-memory globally accumulated transaction graph
_dynamic_graph = nx.DiGraph()

def _demo_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_weighted_edges_from(
        [
            ("acct_1001", "mid_node_1", 1.0),
            ("mid_node_1", "fraud_hub_1", 2.0),
            ("acct_1001", "mid_node_2", 1.5),
            ("mid_node_2", "acct_2002", 1.0),
            ("acct_2002", "fraud_hub_2", 2.0),
            ("acct_3003", "acct_2002", 1.0),
        ]
    )
    return graph

def get_current_graph() -> nx.DiGraph:
    """Returns the current dynamically accumulated graph or the demo graph if empty."""
    global _dynamic_graph
    if _dynamic_graph.number_of_nodes() == 0:
        return _demo_graph()
    return _dynamic_graph

def add_transaction_to_graph(src: str, dst: str, amount: float) -> None:
    """Adds a single transaction edge to the dynamic in-memory graph."""
    global _dynamic_graph
    if _dynamic_graph.has_edge(src, dst):
        _dynamic_graph[src][dst]["weight"] += amount
    else:
        _dynamic_graph.add_edge(src, dst, weight=amount)

def build_graph_from_dataframe(df: pd.DataFrame) -> nx.DiGraph:
    """Populates and returns the dynamic graph from a transaction DataFrame."""
    global _dynamic_graph
    _dynamic_graph.clear()
    
    if "src_account" in df.columns and "dst_account" in df.columns:
        src_col, dst_col = "src_account", "dst_account"
    elif "account_id" in df.columns and "upi_id" in df.columns:
        src_col, dst_col = "account_id", "upi_id"
    elif "Sender_account" in df.columns and "Receiver_account" in df.columns:
        src_col, dst_col = "Sender_account", "Receiver_account"
    else:
        # Fallback to column indices
        cols = list(df.columns)
        if len(cols) >= 2:
            src_col, dst_col = cols[0], cols[1]
        else:
            return _dynamic_graph

    amt_col = "amount" if "amount" in df.columns else ("transaction_amount" if "transaction_amount" in df.columns else ("Amount" if "Amount" in df.columns else None))

    for _, row in df.iterrows():
        src = str(row.get(src_col))
        dst = str(row.get(dst_col))
        weight = float(row.get(amt_col, 1.0)) if amt_col else 1.0
        
        if _dynamic_graph.has_edge(src, dst):
            _dynamic_graph[src][dst]["weight"] += weight
        else:
            _dynamic_graph.add_edge(src, dst, weight=weight)
            
    return _dynamic_graph

def detect_circular_flows(graph: nx.DiGraph) -> List[List[str]]:
    """Detects simple circular flow cycles in the transaction graph."""
    try:
        cycles = list(nx.simple_cycles(graph))
        # Filter for actual cycles (length >= 2) and return up to top 10
        return [c for c in cycles if len(c) >= 2][:10]
    except Exception:
        return []

def find_hub_nodes(graph: nx.DiGraph, threshold: int = 5) -> List[Dict[str, Any]]:
    """Identifies central hub accounts with high degrees of interaction."""
    hubs = []
    for node in graph.nodes():
        in_deg = graph.in_degree(node)
        out_deg = graph.out_degree(node)
        total_deg = in_deg + out_deg
        if total_deg >= threshold:
            hubs.append({
                "account_id": node,
                "in_degree": in_deg,
                "out_degree": out_deg,
                "total_degree": total_deg
            })
    return sorted(hubs, key=lambda x: x["total_degree"], reverse=True)

@dataclass
class GraphRiskResult:
    score: float
    reasoning: List[str]
    contributions: Dict[str, float]

def _shortest_distance_to_flagged(graph: nx.DiGraph, account_id: str) -> float:
    distances: List[float] = []
    # Identify dynamic fraud nodes (e.g. nodes containing 'fraud', 'scam', or standard FLAGGED_NODES)
    dynamic_flagged = set(FLAGGED_NODES)
    for node in graph.nodes():
        if "fraud" in str(node).lower() or "scam" in str(node).lower():
            dynamic_flagged.add(node)
            
    for target in dynamic_flagged:
        if target not in graph or account_id not in graph:
            continue
        try:
            d = nx.shortest_path_length(graph, source=account_id, target=target, weight="weight")
            distances.append(float(d))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    return min(distances) if distances else float("inf")

def evaluate_graph_risk(account_id: str, graph: nx.DiGraph | None = None) -> GraphRiskResult:
    if graph is None:
        graph = get_current_graph()
        
    if account_id not in graph:
        graph.add_node(account_id)

    distance = _shortest_distance_to_flagged(graph, account_id)
    distance_signal = 0.0 if distance == float("inf") else min(1.0, 1.0 / (distance + 0.2))

    try:
        centrality = nx.eigenvector_centrality(graph, max_iter=500, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        centrality = nx.degree_centrality(graph)
    centrality_signal = centrality.get(account_id, 0.0)

    # Dynamic seed scores for TrustRank
    dynamic_flagged = set(FLAGGED_NODES)
    for node in graph.nodes():
        if "fraud" in str(node).lower() or "scam" in str(node).lower():
            dynamic_flagged.add(node)
            
    seed_scores = {node: 1.0 for node in dynamic_flagged}
    trust_scores = _trust_rank(graph, seed_scores)
    trust_signal = trust_scores.get(account_id, 0.0)

    weighted = (0.5 * distance_signal) + (0.3 * centrality_signal) + (0.2 * trust_signal)
    graph_score = round(min(CONFIG.max_score, weighted * CONFIG.max_score), 2)

    reasons = [
        "Graph score evaluates structural network risk based on path proximity, centrality influence, and TrustRank.",
        f"Path distance to flagged nodes is {distance if distance != float('inf') else 'infinite'}.",
        f"Centrality structural influence score is {round(centrality_signal, 4)}."
    ]
    
    # Check for cycles
    cycles = detect_circular_flows(graph)
    for cycle in cycles:
        if account_id in cycle:
            graph_score = min(CONFIG.max_score, graph_score + 15.0)
            reasons.append(f"CRITICAL: Detected in a circular transaction flow cycle: {' -> '.join(cycle)} -> {cycle[0]}")

    contributions = {
        "path_proximity": round(distance_signal * 50.0, 2),
        "centrality": round(centrality_signal * 30.0, 2),
        "trust_rank": round(trust_signal * 20.0, 2),
    }

    return GraphRiskResult(score=graph_score, reasoning=reasons, contributions=contributions)

def _trust_rank(graph: nx.DiGraph, seed_risk: Dict[str, float], damping: float = 0.85, iterations: int = 30) -> Dict[str, float]:
    nodes = list(graph.nodes())
    if not nodes:
        return {}

    scores = {node: max(0.0, min(1.0, seed_risk.get(node, 0.0))) for node in nodes}
    for _ in range(iterations):
        updated: Dict[str, float] = {}
        for node in nodes:
            incoming = 0.0
            for predecessor in graph.predecessors(node):
                out_degree = graph.out_degree(predecessor)
                if out_degree > 0:
                    incoming += scores.get(predecessor, 0.0) / out_degree
            updated[node] = (1.0 - damping) * seed_risk.get(node, 0.0) + damping * incoming
        scores = updated

    max_score = max(scores.values(), default=0.0)
    if max_score <= 0.0:
        return {node: 0.0 for node in nodes}
    return {node: value / max_score for node, value in scores.items()}

