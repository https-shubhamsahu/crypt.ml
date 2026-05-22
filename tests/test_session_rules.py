"""
Tests for Session Rule Injection feature.

Covers:
  1. Rule detection  (detect_rules)
  2. Rule parsing    (parse_rules heuristic fallback)
  3. LLM prompt injection (apply_rules_to_prompt)
  4. Session persistence (SessionRuleStore)
  5. Structured output parsing (format_llm_response)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.session_rules import (
    Rule,
    SessionRuleStore,
    apply_rules_to_prompt,
    chat_with_rules,
    detect_rules,
    format_llm_response,
    parse_rules,
)


# ── 1) Rule Detection ───────────────────────────────────────────────────────

class TestDetectRules:

    def test_empty_string(self) -> None:
        assert detect_rules("") is False

    def test_normal_question(self) -> None:
        assert detect_rules("What is the risk score for account 1001?") is False

    def test_in_this_session(self) -> None:
        assert detect_rules("In this session, prioritize recall >= 0.75") is True

    def test_prioritize(self) -> None:
        assert detect_rules("Prioritize high-risk UPI transactions") is True

    def test_boost(self) -> None:
        assert detect_rules("Boost graph proximity score for 1-hop neighbors") is True

    def test_adjust_threshold(self) -> None:
        assert detect_rules("Adjust threshold to 0.65 for this analysis") is True

    def test_add_rule(self) -> None:
        assert detect_rules("Add rule: flag all crypto transactions above 50k") is True

    def test_set_recall(self) -> None:
        assert detect_rules("Set recall to 0.80") is True

    def test_increase_weight(self) -> None:
        assert detect_rules("Increase weight for the RAW layer") is True

    def test_decrease_weight(self) -> None:
        assert detect_rules("Decrease weight for ML scoring") is True

    def test_focus_on(self) -> None:
        assert detect_rules("Focus on cross-border transfers") is True

    def test_always_consider(self) -> None:
        assert detect_rules("Always consider mule patterns in graph analysis") is True

    def test_case_insensitive(self) -> None:
        assert detect_rules("BOOST the graph score for known mules") is True


# ── 2) Rule Parsing (heuristic fallback, no LLM) ────────────────────────────

class TestParseRulesHeuristic:
    """parse_rules falls back to heuristic when CRYPT_ML_LLM_ENABLED is not set."""

    def test_recall_target(self) -> None:
        rules = parse_rules("Set recall to 0.75 for this session")
        assert len(rules) >= 1
        recall_rule = next((r for r in rules if r.rule_type == "recall_target"), None)
        assert recall_rule is not None
        assert recall_rule.value == 0.75

    def test_graph_proximity_boost(self) -> None:
        rules = parse_rules("Boost 1-hop connections by 20 points")
        assert len(rules) >= 1
        graph_rule = next((r for r in rules if r.rule_type == "graph_proximity_boost"), None)
        assert graph_rule is not None
        assert graph_rule.hops == 1
        assert graph_rule.risk_boost == 20.0

    def test_threshold_change(self) -> None:
        rules = parse_rules("Adjust threshold to 0.55")
        assert len(rules) >= 1
        thresh_rule = next((r for r in rules if r.rule_type == "threshold_change"), None)
        assert thresh_rule is not None
        assert thresh_rule.value == 0.55

    def test_weight_adjustment(self) -> None:
        rules = parse_rules("Increase raw weight in this session")
        weight_rule = next((r for r in rules if r.rule_type == "weight_adjustment"), None)
        assert weight_rule is not None
        assert "RAW" in weight_rule.description

    def test_focus_area(self) -> None:
        rules = parse_rules("Focus on crypto transactions above 100k")
        focus_rule = next((r for r in rules if r.rule_type == "focus_area"), None)
        assert focus_rule is not None
        assert "crypto" in focus_rule.description.lower()

    def test_generic_fallback(self) -> None:
        rules = parse_rules("In this session, apply extra scrutiny to dormant accounts")
        assert len(rules) >= 1

    def test_no_rules_in_normal_text(self) -> None:
        rules = parse_rules("How is the weather today?")
        assert len(rules) == 0

    def test_multiple_rules(self) -> None:
        rules = parse_rules(
            "Set recall to 0.80 and boost 2-hop connections by 15"
        )
        types = {r.rule_type for r in rules}
        assert "recall_target" in types
        assert "graph_proximity_boost" in types


# ── 3) LLM Prompt Injection ─────────────────────────────────────────────────

class TestApplyRulesToPrompt:

    def test_no_rules_passthrough(self) -> None:
        prompt = "Analyze this transaction"
        result = apply_rules_to_prompt([], prompt)
        assert result == prompt

    def test_single_rule_injection(self) -> None:
        rules = [Rule(rule_type="recall_target", value=0.75, description="Recall >= 0.75")]
        prompt = "Analyze this transaction"
        result = apply_rules_to_prompt(rules, prompt)
        assert "ACTIVE SESSION RULES" in result
        assert "recall_target" in result
        assert "0.75" in result
        assert prompt in result

    def test_multiple_rules_injection(self) -> None:
        rules = [
            Rule(rule_type="recall_target", value=0.8, description="Recall >= 0.8"),
            Rule(
                rule_type="graph_proximity_boost",
                hops=1,
                risk_boost=20,
                description="Boost 1-hop by 20",
            ),
        ]
        prompt = "Analyze"
        result = apply_rules_to_prompt(rules, prompt)
        assert "Rule 1:" in result
        assert "Rule 2:" in result
        assert "END SESSION RULES" in result

    def test_rule_with_extra_fields(self) -> None:
        rules = [
            Rule(
                rule_type="weight_adjustment",
                description="Increase RAW weight",
                extra={"direction": "increase", "layer": "raw"},
            )
        ]
        result = apply_rules_to_prompt(rules, "test prompt")
        assert "weight_adjustment" in result
        assert "increase" in result


# ── 4) Session Rule Persistence ──────────────────────────────────────────────

class TestSessionRuleStore:

    def _make_store(self, tmp_path: Path, session_id: str = "test") -> SessionRuleStore:
        """Create a store using a temp directory for isolation."""
        with patch("app.services.session_rules._PERSISTENCE_DIR", tmp_path):
            return SessionRuleStore(session_id=session_id)

    def test_empty_store(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        assert store.get_rules() == []

    def test_add_and_retrieve(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        rule = Rule(rule_type="recall_target", value=0.75, description="Recall >= 0.75")
        all_rules = store.add_rules([rule])
        assert len(all_rules) == 1
        assert all_rules[0].rule_type == "recall_target"

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        store1 = self._make_store(tmp_path, "persist_test")
        store1.add_rules([Rule(rule_type="custom", description="Test rule")])

        # New instance should load from disk
        with patch("app.services.session_rules._PERSISTENCE_DIR", tmp_path):
            store2 = SessionRuleStore(session_id="persist_test")
        assert len(store2.get_rules()) == 1
        assert store2.get_rules()[0].description == "Test rule"

    def test_clear(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.add_rules([Rule(rule_type="custom", description="Temp")])
        assert len(store.get_rules()) == 1
        store.clear()
        assert len(store.get_rules()) == 0

    def test_remove_rule(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.add_rules([
            Rule(rule_type="a", description="First"),
            Rule(rule_type="b", description="Second"),
        ])
        assert store.remove_rule(0) is True
        remaining = store.get_rules()
        assert len(remaining) == 1
        assert remaining[0].rule_type == "b"

    def test_remove_invalid_index(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        assert store.remove_rule(99) is False

    def test_json_file_written(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "file_check")
        store.add_rules([Rule(rule_type="custom", description="Persist me")])
        json_file = tmp_path / "file_check.json"
        assert json_file.exists()
        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data[0]["rule_type"] == "custom"


# ── 5) Structured Output Parsing ────────────────────────────────────────────

class TestFormatLlmResponse:

    def test_full_structured_response(self) -> None:
        raw = (
            "[PLAN]\n"
            "Step 1: Check recall.\n"
            "Step 2: Evaluate graph.\n\n"
            "[RESULT]\n"
            "Risk is 72/100.\n\n"
            "[SUGGESTED NEXT]\n"
            "- Check 1-hop neighbors\n"
            "- Review SHAP values\n"
        )
        sections = format_llm_response(raw)
        assert "Check recall" in sections["plan"]
        assert "72/100" in sections["result"]
        assert "1-hop" in sections["suggested_next"]

    def test_partial_response_result_only(self) -> None:
        raw = "[RESULT]\nThe account is high risk."
        sections = format_llm_response(raw)
        assert sections["result"] == "The account is high risk."
        assert sections["plan"] == ""

    def test_fallback_unstructured(self) -> None:
        raw = "This is a plain response with no sections."
        sections = format_llm_response(raw)
        assert sections["result"] == raw
        assert sections["plan"] == ""
        assert sections["suggested_next"] == ""


# ── 6) Rule Data Model ──────────────────────────────────────────────────────

class TestRuleModel:

    def test_to_dict_strips_none(self) -> None:
        rule = Rule(rule_type="recall_target", value=0.8, description="Test")
        d = rule.to_dict()
        assert "hops" not in d
        assert "risk_boost" not in d
        assert d["value"] == 0.8

    def test_from_dict_roundtrip(self) -> None:
        original = Rule(
            rule_type="graph_proximity_boost",
            hops=2,
            risk_boost=15.0,
            description="Boost 2-hop by 15",
        )
        d = original.to_dict()
        restored = Rule.from_dict(d)
        assert restored.rule_type == original.rule_type
        assert restored.hops == original.hops
        assert restored.risk_boost == original.risk_boost

    def test_from_dict_unknown_keys_go_to_extra(self) -> None:
        d = {
            "rule_type": "custom",
            "description": "Test",
            "custom_field": "hello",
        }
        rule = Rule.from_dict(d)
        assert rule.extra["custom_field"] == "hello"


# ── 7) Chat Integration (fallback path) ─────────────────────────────────────

class TestChatWithRules:

    def test_fallback_response_structured(self) -> None:
        """When LLM is disabled, chat_with_rules returns structured fallback."""
        response = chat_with_rules(
            user_message="What is the risk for acct_1001?",
            session_rules=[],
        )
        assert "[PLAN]" in response
        assert "[RESULT]" in response
        assert "[SUGGESTED NEXT]" in response

    def test_fallback_includes_rules(self) -> None:
        rules = [Rule(rule_type="recall_target", value=0.75, description="Recall >= 0.75")]
        response = chat_with_rules(
            user_message="Analyze risk",
            session_rules=rules,
        )
        assert "recall_target" in response

    def test_fallback_with_system_context(self) -> None:
        response = chat_with_rules(
            user_message="Hello",
            session_rules=[],
            system_context="You are crypt.ml",
            ml_artifacts="ROC-AUC=0.929",
        )
        assert "[PLAN]" in response


# ── 8) NLP Service Integration ───────────────────────────────────────────────

class TestNlpServiceIntegration:

    def test_set_and_get_session_rules(self) -> None:
        from app.services.nlp_service import get_session_rules, set_session_rules

        rules = [Rule(rule_type="test", description="Integration test")]
        set_session_rules(rules)
        retrieved = get_session_rules()
        assert len(retrieved) == 1
        assert retrieved[0].rule_type == "test"
        # Cleanup
        set_session_rules([])

    def test_analyze_note_risk_accepts_rules(self) -> None:
        from app.services.nlp_service import analyze_note_risk

        rules = [Rule(rule_type="focus_area", description="Focus on crypto")]
        result = analyze_note_risk("urgent crypto transfer", session_rules=rules)
        assert result.score > 0
        assert "crypto" in result.matched_terms or "urgent" in result.matched_terms
