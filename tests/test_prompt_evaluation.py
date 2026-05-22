"""Prompt evaluation harness for crypt.ml agent prompts.

Validates that prompt files are well-formed, contain required sections,
and that the agent behavior constraints are internally consistent.

Run:
    python -m pytest tests/test_prompt_evaluation.py -v
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pytest

PROMPTS_DIR = Path(".")  / ".github" / "prompts"
AGENTS_DIR = Path(".") / ".github" / "agents"

KNOWN_AGENTS = {
    "implementation",
    "planner",
    "security-reviewer",
    "demo-strategist",
    "ml",
}

REQUIRED_SYSTEM_CONTEXT_SECTIONS = [
    "Architecture Map",
    "API Endpoints",
    "UI Flow",
    "Behavior Rules",
    "Response Format",
]

FORBIDDEN_CORE_FILES = [
    "raw_service.py",
    "ml_service.py",
    "graph_service.py",
    "risk_aggregator.py",
    "weight_manager.py",
    "orchestrator.py",
    "case_store.py",
    "train_ml.py",
]

STRUCTURED_RESPONSE_MARKERS = ["[PLAN]", "[RESULT]", "[SUGGESTED NEXT]"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_prompt_files() -> Dict[str, str]:
    """Return {filename: content} for all .prompt.md files."""
    if not PROMPTS_DIR.exists():
        return {}
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(PROMPTS_DIR.glob("*.prompt.md"))
    }


def _load_agent_files() -> Dict[str, str]:
    if not AGENTS_DIR.exists():
        return {}
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(AGENTS_DIR.glob("*.agent.md"))
    }


def _extract_frontmatter(content: str) -> Dict[str, str]:
    """Extract YAML-style frontmatter between --- delimiters."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    lines = match.group(1).strip().splitlines()
    result: Dict[str, str] = {}
    for line in lines:
        parts = line.split(":", 1)
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


# ---------------------------------------------------------------------------
# Prompt file discovery
# ---------------------------------------------------------------------------

ALL_PROMPTS = _load_prompt_files()
ALL_AGENTS = _load_agent_files()


# ---------------------------------------------------------------------------
# Tests: Structural validation
# ---------------------------------------------------------------------------

class TestPromptStructure:
    """Every .prompt.md must have valid frontmatter and content."""

    @pytest.mark.parametrize("filename", list(ALL_PROMPTS.keys()))
    def test_has_frontmatter(self, filename: str) -> None:
        content = ALL_PROMPTS[filename]
        assert content.startswith("---"), f"{filename} missing frontmatter delimiter"
        fm = _extract_frontmatter(content)
        assert "name" in fm, f"{filename} frontmatter missing 'name'"
        assert "description" in fm, f"{filename} frontmatter missing 'description'"

    @pytest.mark.parametrize("filename", list(ALL_PROMPTS.keys()))
    def test_name_matches_filename(self, filename: str) -> None:
        fm = _extract_frontmatter(ALL_PROMPTS[filename])
        expected_name = filename.replace(".prompt.md", "").replace("-", "_")
        actual_name = fm.get("name", "").replace("-", "_")
        assert actual_name == expected_name, (
            f"{filename}: frontmatter name '{fm.get('name')}' "
            f"doesn't match filename stem '{expected_name}'"
        )

    @pytest.mark.parametrize("filename", list(ALL_PROMPTS.keys()))
    def test_not_empty_body(self, filename: str) -> None:
        content = ALL_PROMPTS[filename]
        body = re.sub(r"^---.*?---\s*", "", content, count=1, flags=re.DOTALL)
        assert len(body.strip()) > 50, f"{filename} has too little content after frontmatter"


class TestAgentStructure:
    """Every .agent.md must have valid frontmatter."""

    @pytest.mark.parametrize("filename", list(ALL_AGENTS.keys()))
    def test_has_frontmatter(self, filename: str) -> None:
        content = ALL_AGENTS[filename]
        fm = _extract_frontmatter(content)
        assert "name" in fm, f"{filename} frontmatter missing 'name'"
        assert "description" in fm, f"{filename} frontmatter missing 'description'"


# ---------------------------------------------------------------------------
# Tests: System context prompt integrity
# ---------------------------------------------------------------------------

class TestSystemContextPrompt:
    """The apply_system_context prompt must be comprehensive and correct."""

    PROMPT_FILE = "apply_system_context.prompt.md"

    @pytest.fixture()
    def content(self) -> str:
        assert self.PROMPT_FILE in ALL_PROMPTS, "apply_system_context.prompt.md not found"
        return ALL_PROMPTS[self.PROMPT_FILE]

    def test_contains_all_required_sections(self, content: str) -> None:
        for section in REQUIRED_SYSTEM_CONTEXT_SECTIONS:
            assert section in content, f"Missing required section: '{section}'"

    def test_references_core_service_files(self, content: str) -> None:
        expected_refs = [
            "raw_service.py",
            "ml_service.py",
            "graph_service.py",
            "nlp_service.py",
            "risk_aggregator.py",
            "orchestrator.py",
            "weight_manager.py",
            "case_store.py",
            "train_ml.py",
            "raw_rules.json",
        ]
        for ref in expected_refs:
            assert ref in content, f"System context should reference '{ref}'"

    def test_references_api_endpoints(self, content: str) -> None:
        endpoints = ["/api/v1/health", "/api/v1/scam-exposure", "/api/v1/feedback", "/api/v1/weights"]
        for ep in endpoints:
            assert ep in content, f"System context should reference endpoint '{ep}'"

    def test_contains_response_format_markers(self, content: str) -> None:
        for marker in STRUCTURED_RESPONSE_MARKERS:
            assert marker in content, f"Missing response format marker: '{marker}'"

    def test_behavior_rules_forbid_core_modification(self, content: str) -> None:
        assert "Never modify backend core service files" in content or "Never change backend" in content, (
            "System context must explicitly forbid core file modification"
        )

    def test_risk_formula_present(self, content: str) -> None:
        assert "Risk_final" in content, "System context must contain the risk aggregation formula"


# ---------------------------------------------------------------------------
# Tests: Flow-specific prompts
# ---------------------------------------------------------------------------

class TestFlowPrompts:
    """Flow-specific prompts must follow conventions."""

    FLOW_PROMPTS = [
        "analyze_recall_trend.prompt.md",
        "explain_shap.prompt.md",
        "suggest_threshold_change.prompt.md",
    ]

    @pytest.mark.parametrize("filename", FLOW_PROMPTS)
    def test_exists(self, filename: str) -> None:
        assert filename in ALL_PROMPTS, f"Flow prompt '{filename}' not found in .github/prompts/"

    @pytest.mark.parametrize("filename", FLOW_PROMPTS)
    def test_has_response_format(self, filename: str) -> None:
        content = ALL_PROMPTS[filename]
        for marker in STRUCTURED_RESPONSE_MARKERS:
            assert marker in content, f"{filename} missing '{marker}' in response format"

    @pytest.mark.parametrize("filename", FLOW_PROMPTS)
    def test_has_constraints_section(self, filename: str) -> None:
        content = ALL_PROMPTS[filename]
        assert "Constraint" in content, f"{filename} missing Constraints section"

    @pytest.mark.parametrize("filename", FLOW_PROMPTS)
    def test_no_core_file_modification_allowed(self, filename: str) -> None:
        content = ALL_PROMPTS[filename]
        assert "Do NOT modify" in content or "Never modify" in content, (
            f"{filename} must explicitly forbid core file modification"
        )


# ---------------------------------------------------------------------------
# Tests: Session template prompt
# ---------------------------------------------------------------------------

class TestSessionTemplate:
    """Session template must have input placeholders and session-aware logic."""

    PROMPT_FILE = "session_template.prompt.md"

    @pytest.fixture()
    def content(self) -> str:
        assert self.PROMPT_FILE in ALL_PROMPTS, "session_template.prompt.md not found"
        return ALL_PROMPTS[self.PROMPT_FILE]

    def test_has_input_placeholders(self, content: str) -> None:
        placeholders = re.findall(r"\$\{input:\w+\}", content)
        assert len(placeholders) >= 5, (
            f"Session template should have at least 5 input placeholders, found {len(placeholders)}"
        )

    def test_references_artifacts(self, content: str) -> None:
        assert "ml_model.joblib" in content
        assert "ml_model_metadata.json" in content

    def test_has_session_resume_format(self, content: str) -> None:
        assert "[SESSION RESUME]" in content or "[RESULT]" in content

    def test_suggests_next_actions(self, content: str) -> None:
        assert "[SUGGESTED NEXT]" in content


# ---------------------------------------------------------------------------
# Tests: Cross-prompt consistency
# ---------------------------------------------------------------------------

class TestCrossPromptConsistency:
    """Verify prompts are consistent with each other and the codebase."""

    def test_all_prompts_reference_valid_agents(self) -> None:
        for filename, content in ALL_PROMPTS.items():
            fm = _extract_frontmatter(content)
            agent = fm.get("agent")
            if agent:
                assert agent in KNOWN_AGENTS or agent == "implementation", (
                    f"{filename} references unknown agent '{agent}'. "
                    f"Known agents: {KNOWN_AGENTS}"
                )

    def test_no_duplicate_prompt_names(self) -> None:
        names: List[str] = []
        for content in ALL_PROMPTS.values():
            fm = _extract_frontmatter(content)
            name = fm.get("name")
            if name:
                names.append(name)
        assert len(names) == len(set(names)), f"Duplicate prompt names: {names}"

    def test_risk_formula_consistent(self) -> None:
        """Every prompt that mentions risk formula should use the canonical form."""
        canonical = "w1*RAW + w2*ML + w3*GRAPH"
        for filename, content in ALL_PROMPTS.items():
            if "Risk_final" in content:
                assert canonical in content or "w1 * RAW" in content, (
                    f"{filename} mentions Risk_final but uses non-canonical formula"
                )
