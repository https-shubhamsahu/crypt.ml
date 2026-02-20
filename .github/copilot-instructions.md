# Copilot Instructions for AEGIS-AML

## Repo Reality (Current Stage)
- This repository currently contains project-definition assets only (no executable app code yet).
- Source of truth for product and architecture: `.github/PROJECT_CONTEXT.md`.
- Agent behavior specs live in `.github/agents/*.agent.md`.
- Reusable prompt entrypoints live in `.github/prompts/*.prompt.md`.

## Big-Picture Architecture to Preserve
- Implement the 3-layer AML model exactly as defined in `PROJECT_CONTEXT.md`:
  1. RAW (deterministic guardrails)
  2. SAR/ML (probabilistic score + explainability)
  3. Graph Intelligence (relational risk)
- Keep risk aggregation explainable and bounded via:
  - `Risk_final = w1*RAW + w2*ML + w3*GRAPH`
  - Normalized score range `0-100`.
- Preserve human-in-the-loop flow and dynamic weight recalibration semantics.

## Expected Code Organization (when generating new code)
- Prefer modular boundaries reflected in project context:
  - API layer (FastAPI routers + Pydantic schemas)
  - Service layer (risk logic, graph logic, orchestration)
  - Explainability outputs (feature/graph contribution narratives)
- Do not collapse logic into monolithic files.
- Keep risk computation isolated in service modules, not route handlers.

## Project-Specific Conventions
- Always include Python type hints.
- Avoid magic numbers in risk logic; use named constants/config.
- Keep outputs regulator-friendly: include concise reasoning alongside scores.
- For graph work, model nodes/edges and metrics explicitly (path, community, centrality).
- For ML work, keep explainability first-class (SHAP-style feature contribution output).

## Agent/Prompt Workflow Conventions
- Planning-first workflow is preferred:
  - `planner.agent.md` defines structure and dependencies before implementation.
  - `implementation.agent.md` performs code changes with clean architecture constraints.
  - `security.agent.md` reviews logic bypass/injection/integrity risks.
- Prompt files define the intended task shape; follow them rather than ad-hoc output formats.
  - Example: `build-api.prompt.md` enforces schema/service/router separation.
  - Example: `risk-logic.prompt.md` enforces weighted formula + normalization.

## Developer Workflow Guidance
- Do not invent build/test/run commands if no project runtime files are present.
- Before suggesting commands, verify existence of `pyproject.toml`, `requirements.txt`, `Makefile`, or test config.
- If missing, generate minimal scaffolding first, then provide concrete commands.

## MCP Usage Policy (Hackathon MVP)
- Keep MVP work local by default; do not use MCP unless the task explicitly needs it.
- Use MCP only for:
  - database access
  - PaySim querying
  - live Neo4j graph queries
  - GitHub issue tracking integration
- For core prototype logic (risk scoring, local graph analysis, API scaffolding), prefer local files/scripts and in-process libraries.

## Change Discipline
- Keep edits small and scoped to the requested feature.
- Align naming and module structure with existing `.github` context files.
- If requirements conflict, prioritize `PROJECT_CONTEXT.md` over generic framework defaults.
