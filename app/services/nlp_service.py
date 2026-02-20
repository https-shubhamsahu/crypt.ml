from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import List, Optional, Set
import re
from urllib import error, request

from app.services.session_rules import Rule, apply_rules_to_prompt


RISK_LEXICON = {
    "urgent": 12.0,
    "cashout": 18.0,
    "mule": 22.0,
    "otp": 10.0,
    "giftcard": 16.0,
    "crypto": 14.0,
    "bypass": 20.0,
    "fake": 12.0,
    "freeze": 10.0,
    "untraceable": 24.0,
}

LLM_SCORE_WEIGHT = 0.40
LEXICON_SCORE_WEIGHT = 0.60
LLM_TIMEOUT_SECONDS = 20

# Module-level session rules reference; updated by the dashboard/chat layer
_active_session_rules: List[Rule] = []


def _is_llm_enabled() -> bool:
    raw = os.getenv("AEGIS_LLM_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def set_session_rules(rules: List[Rule]) -> None:
    """Update the module-level session rules used for LLM prompt injection."""
    global _active_session_rules
    _active_session_rules = list(rules)


def get_session_rules() -> List[Rule]:
    """Return current session rules applied to NLP analysis."""
    return list(_active_session_rules)


@dataclass
class NLPRiskResult:
    score: float
    matched_terms: List[str]
    llm_summary: str | None = None


def analyze_note_risk(
    note: str | None,
    session_rules: Optional[List[Rule]] = None,
) -> NLPRiskResult:
    """Analyse transaction note risk.  Optionally inject *session_rules* into the LLM prompt."""
    if not note:
        return NLPRiskResult(score=0.0, matched_terms=[])

    # Determine which rules to use: explicit arg > module-level singleton
    rules = session_rules if session_rules is not None else _active_session_rules

    tokens = _tokenize(note)
    matched_terms: List[str] = []
    score = 0.0

    for token in tokens:
        if token in RISK_LEXICON:
            matched_terms.append(token)
            score += RISK_LEXICON[token]

    lexicon_score = min(100.0, round(score, 2))
    llm_score, llm_terms, llm_summary = _analyze_with_local_llm(note, rules=rules)

    blended_score = (LEXICON_SCORE_WEIGHT * lexicon_score) + (LLM_SCORE_WEIGHT * llm_score)
    bounded_score = min(100.0, round(blended_score, 2))

    merged_terms = sorted(set(matched_terms + llm_terms))
    return NLPRiskResult(score=bounded_score, matched_terms=merged_terms, llm_summary=llm_summary)


def _tokenize(text: str) -> Set[str]:
    return set(re.findall(r"[a-zA-Z]+", text.lower()))


def _analyze_with_local_llm(
    note: str,
    rules: Optional[List[Rule]] = None,
) -> tuple[float, List[str], str | None]:
    """Call local Ollama for NLP risk analysis, injecting session rules into the prompt."""
    llm_enabled = _is_llm_enabled()
    if not llm_enabled:
        return 0.0, [], None

    endpoint = os.getenv("AEGIS_LLM_ENDPOINT", "http://localhost:11434/api/generate")
    model = os.getenv("AEGIS_LLM_MODEL", "phi3.5")

    base_prompt = (
        "You are an AML NLP analyzer. Return STRICT JSON with keys: "
        "risk_signal_0_100 (number), suspicious_terms (array of strings), summary (string). "
        "Do not return markdown. Text:\n"
        f"{note}"
    )

    # Inject session rules into prompt when available
    prompt = apply_rules_to_prompt(rules or [], base_prompt)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    try:
        req = request.Request(
            url=endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        raw_response = body.get("response", "{}")
        parsed = json.loads(raw_response)

        score = float(parsed.get("risk_signal_0_100", 0.0))
        terms = [str(item).strip().lower() for item in parsed.get("suspicious_terms", []) if str(item).strip()]
        summary = str(parsed.get("summary", "")).strip() or None
        bounded_score = min(100.0, max(0.0, round(score, 2)))
        return bounded_score, terms, summary
    except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        return 0.0, [], None
