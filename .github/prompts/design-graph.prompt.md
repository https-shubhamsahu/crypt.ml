---
name: design-graph
description: Design or extend Graph Intelligence architecture
agent: planner
argument-hint: feature=Describe the graph feature
---

You are designing the Graph Intelligence layer for AEGIS-AML.

Feature request:
${input:feature}

Your job is to produce a structured architectural design.

Output must include:

1. Objective  
   - What problem this graph feature solves

2. Node Model  
   - Node types (Account, Transaction, Device, etc.)
   - Required attributes per node

3. Edge Model  
   - Edge direction
   - Edge attributes (amount, timestamp, frequency)

4. Required Graph Metrics  
   - Shortest Path
   - Community Detection
   - Centrality (Eigenvector / PageRank)
   - Any additional structural metrics

5. Risk Contribution  
   - How each metric affects final risk score
   - Suggested weighting logic

6. Computational Considerations  
   - Time complexity
   - Memory constraints
   - Batch vs real-time computation

7. Edge Cases  
   - No-path scenario
   - New account cold-start problem
   - Large dense clusters

Do NOT write code.
Focus strictly on system design.
Use clean numbered sections.
