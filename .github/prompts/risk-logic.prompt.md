---
name: risk-logic
description: Add or refine dynamic AML risk scoring logic
agent: implementation
tools: ['edit']
argument-hint: change=Describe the change needed
---

Modify or enhance the AML risk scoring engine.

Requested change:
${input:change}

Constraints:

1. Maintain dynamic weighted formula:
   Risk_final = w1*RAW + w2*ML + w3*GRAPH

2. Avoid hardcoded magic numbers
3. Keep logic explainable
4. Ensure score normalization (0–100)
5. Keep modular and testable

Deliver:

- Updated function implementation
- Clear explanation of weighting logic
- Example test case

If improving graph contribution:
- Show how centrality, path distance, or clustering affects score.

Keep implementation minimal but robust.
