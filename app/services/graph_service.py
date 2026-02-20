from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

import networkx as nx

from app.core.config import CONFIG


FLAGGED_NODES: Set[str] = {"fraud_hub_1", "fraud_hub_2"}


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


@dataclass
class GraphRiskResult:
    score: float
    reasoning: List[str]
    contributions: Dict[str, float]


def _shortest_distance_to_flagged(graph: nx.DiGraph, account_id: str) -> float:
    distances: List[float] = []
    for target in FLAGGED_NODES:
        if target not in graph or account_id not in graph:
            continue
        try:
            d = nx.shortest_path_length(graph, source=account_id, target=target, weight="weight")
            distances.append(float(d))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    return min(distances) if distances else float("inf")


def evaluate_graph_risk(account_id: str) -> GraphRiskResult:
    graph = _demo_graph()
    if account_id not in graph:
        graph.add_node(account_id)

    distance = _shortest_distance_to_flagged(graph, account_id)
    distance_signal = 0.0 if distance == float("inf") else min(1.0, 1.0 / (distance + 0.2))

    try:
        centrality = nx.eigenvector_centrality(graph, max_iter=500, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        centrality = nx.degree_centrality(graph)
    centrality_signal = centrality.get(account_id, 0.0)

    seed_scores = {node: 1.0 for node in FLAGGED_NODES}
    trust_scores = _trust_rank(graph, seed_scores)
    trust_signal = trust_scores.get(account_id, 0.0)

    weighted = (0.5 * distance_signal) + (0.3 * centrality_signal) + (0.2 * trust_signal)
    graph_score = round(min(CONFIG.max_score, weighted * CONFIG.max_score), 2)

    reasons = [
        "Graph score uses path proximity, centrality influence, and trust propagation.",
        "Closer links to flagged nodes increase structural risk.",
    ]
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
