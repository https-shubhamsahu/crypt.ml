from pathlib import Path
import sys

import networkx as nx

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from sample_scripts import (
    normalized_eigenvector_centrality,
    shortest_path_distance_to_flagged,
    trust_rank,
)


def main() -> None:
    graph = nx.DiGraph()
    graph.add_weighted_edges_from(
        [
            ("acct_A", "acct_B", 1.0),
            ("acct_B", "acct_C", 1.0),
            ("acct_C", "acct_D", 2.0),
            ("acct_E", "acct_B", 3.0),
        ]
    )

    flagged = {"acct_D"}
    seed_risk = {"acct_D": 1.0}

    distance = shortest_path_distance_to_flagged(graph, "acct_A", flagged)
    centrality = normalized_eigenvector_centrality(graph)
    tr_scores = trust_rank(graph, seed_risk)

    print("Shortest path distance to flagged:", distance)
    print("Centrality scores:", centrality)
    print("Trust rank scores:", tr_scores)


if __name__ == "__main__":
    main()
