from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence

import networkx as nx


def shortest_path_distance_to_flagged(
    graph: nx.DiGraph,
    source_node: str,
    flagged_nodes: Iterable[str],
    weight: str = "weight",
) -> float:
    """Return the shortest weighted distance from source to any flagged node.

    Returns float("inf") when no flagged node is reachable.
    """
    distances: list[float] = []
    for node in flagged_nodes:
        if node in graph:
            try:
                distance = nx.shortest_path_length(graph, source=source_node, target=node, weight=weight)
                distances.append(float(distance))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

    if not distances:
        return float("inf")
    return min(distances)


def normalized_eigenvector_centrality(
    graph: nx.DiGraph,
    max_iter: int = 500,
    tolerance: float = 1e-6,
) -> Dict[str, float]:
    """Compute eigenvector centrality and normalize values into [0, 1]."""
    if graph.number_of_nodes() == 0:
        return {}

    try:
        centrality = nx.eigenvector_centrality(graph, max_iter=max_iter, tol=tolerance)
    except nx.PowerIterationFailedConvergence:
        centrality = nx.degree_centrality(graph)
    max_value = max(centrality.values(), default=0.0)

    if max_value <= 0.0:
        return {node: 0.0 for node in centrality}

    return {node: float(value / max_value) for node, value in centrality.items()}


def trust_rank(
    graph: nx.DiGraph,
    seed_risk: Mapping[str, float],
    damping: float = 0.85,
    iterations: int = 30,
) -> Dict[str, float]:
    """Propagate risk from seed nodes across outgoing links (TrustRank-style).

    - `seed_risk` should contain node -> [0, 1] initial risk priors.
    - Returns normalized node scores in [0, 1].
    """
    nodes: Sequence[str] = list(graph.nodes())
    if not nodes:
        return {}

    node_set = set(nodes)
    normalized_seed = {node: max(0.0, min(1.0, float(seed_risk.get(node, 0.0)))) for node in node_set}

    scores: Dict[str, float] = dict(normalized_seed)
    for _ in range(iterations):
        updated_scores: Dict[str, float] = {}
        for node in nodes:
            incoming_total = 0.0
            for predecessor in graph.predecessors(node):
                out_degree = graph.out_degree(predecessor)
                if out_degree > 0:
                    incoming_total += scores.get(predecessor, 0.0) / out_degree

            updated_scores[node] = (1.0 - damping) * normalized_seed.get(node, 0.0) + damping * incoming_total

        scores = updated_scores

    max_score = max(scores.values(), default=0.0)
    if max_score <= 0.0:
        return {node: 0.0 for node in nodes}

    return {node: float(value / max_score) for node, value in scores.items()}
