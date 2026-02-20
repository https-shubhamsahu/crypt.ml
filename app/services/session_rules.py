"""
Session Rule Injection via LLM Chat
====================================
Work Plan (implements feature spec from hackathon_dashboard chat integration):
  1. detect_rules()   – keyword heuristic to flag user text as rule directive
  2. parse_rules()    – LLM-backed parse → structured Rule objects
  3. apply_rules_to_prompt() – serialise active rules into LLM prompt prefix
  4. SessionRuleStore – thread-safe, JSON-file-backed persistence per session
  5. format_llm_response() – enforce [PLAN]/[RESULT]/[SUGGESTED NEXT] output

Integration points:
  • nlp_service.py  – prompt prefix injection
  • hackathon_dashboard.py  – Chat tab, sidebar rule display
  • Persistence file: data/session_rules/<session_id>.json
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib import error, request

# ── Constants ────────────────────────────────────────────────────────────────

# Phrases that signal the user is injecting a session rule
_RULE_TRIGGER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bin\s+this\s+session\b", re.IGNORECASE),
    re.compile(r"\bprioritize\b", re.IGNORECASE),
    re.compile(r"\bboost\b", re.IGNORECASE),
    re.compile(r"\badjust\s+threshold\b", re.IGNORECASE),
    re.compile(r"\badd\s+rule\b", re.IGNORECASE),
    re.compile(r"\bset\s+recall\b", re.IGNORECASE),
    re.compile(r"\bset\s+threshold\b", re.IGNORECASE),
    re.compile(r"\bincrease\s+weight\b", re.IGNORECASE),
    re.compile(r"\bdecrease\s+weight\b", re.IGNORECASE),
    re.compile(r"\brisk.?boost\b", re.IGNORECASE),
    re.compile(r"\bgraph.?proximity\b", re.IGNORECASE),
    re.compile(r"\bfocus\s+on\b", re.IGNORECASE),
    re.compile(r"\bignore\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+analyzing\b", re.IGNORECASE),
    re.compile(r"\balways\s+consider\b", re.IGNORECASE),
]

LLM_TIMEOUT_SECONDS = int(os.getenv("AEGIS_LLM_TIMEOUT_SECONDS", "45"))
LLM_NUM_PREDICT = int(os.getenv("AEGIS_LLM_NUM_PREDICT", "384"))
_PERSISTENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "session_rules"


def _is_llm_enabled() -> bool:
    """Enable LLM unless explicitly disabled; keep tests deterministic."""
    raw = os.getenv("AEGIS_LLM_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True

# ── Data Model ───────────────────────────────────────────────────────────────


@dataclass
class Rule:
    """Single parsed session rule."""

    rule_type: str
    description: str
    value: Optional[float] = None
    hops: Optional[int] = None
    risk_boost: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Strip None-valued optional fields for cleanliness
        return {k: v for k, v in d.items() if v is not None and v != {}}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        known_keys = {"rule_type", "description", "value", "hops", "risk_boost"}
        extra = {k: v for k, v in data.items() if k not in known_keys and k != "extra"}
        extra.update(data.get("extra", {}))
        return cls(
            rule_type=data.get("rule_type", "custom"),
            description=data.get("description", ""),
            value=data.get("value"),
            hops=data.get("hops"),
            risk_boost=data.get("risk_boost"),
            extra=extra if extra else {},
        )


# ── 1) Rule Detection ───────────────────────────────────────────────────────


def detect_rules(user_text: str) -> bool:
    """Return True when *user_text* contains session-rule directive phrases."""
    if not user_text:
        return False
    return any(pattern.search(user_text) for pattern in _RULE_TRIGGER_PATTERNS)


# ── 2) Rule Parsing (LLM-backed, with fallback) ────────────────────────────


def parse_rules(user_text: str) -> List[Rule]:
    """Parse natural-language rule directives into structured Rule objects.

    Attempts an Ollama LLM call first; falls back to regex heuristic extraction.
    """
    llm_rules = _parse_rules_via_llm(user_text)
    if llm_rules:
        return llm_rules
    return _parse_rules_heuristic(user_text)


def _parse_rules_via_llm(user_text: str) -> List[Rule]:
    """Call local Ollama to convert natural-language rules to JSON."""
    llm_enabled = _is_llm_enabled()
    if not llm_enabled:
        return []

    endpoint = os.getenv("AEGIS_LLM_ENDPOINT", "http://localhost:11434/api/generate")
    model = os.getenv("AEGIS_LLM_MODEL", "phi3.5")

    prompt = (
        "You are a rule-extraction engine for the AEGIS-AML system. "
        "Parse the user's natural-language session rule directive into a JSON array. "
        "Each element must have at minimum: rule_type (string), description (string). "
        "Optional fields: value (number), hops (integer), risk_boost (number). "
        "Known rule_type values: recall_target, graph_proximity_boost, weight_adjustment, "
        "threshold_change, focus_area, custom. "
        "Return ONLY a JSON array, no markdown.\n\n"
        f"User directive: {user_text}"
    )

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

        raw = body.get("response", "[]")
        parsed = json.loads(raw)

        # Handle both {"rules": [...]} wrapper and bare array
        if isinstance(parsed, dict):
            parsed = parsed.get("rules", parsed.get("result", []))
        if not isinstance(parsed, list):
            return []

        return [Rule.from_dict(item) for item in parsed if isinstance(item, dict)]
    except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        return []


def _parse_rules_heuristic(user_text: str) -> List[Rule]:
    """Regex-based fallback rule extraction when LLM is unavailable."""
    rules: List[Rule] = []
    text = user_text.lower()

    # recall target: "set recall 0.75", "prioritize recall >= 0.8"
    recall_match = re.search(r"recall\s*(?:>=?|to|at|of)?\s*(0\.\d+)", text)
    if recall_match:
        rules.append(Rule(
            rule_type="recall_target",
            value=float(recall_match.group(1)),
            description=f"Prioritize recall >= {recall_match.group(1)}",
        ))

    # graph proximity boost: "boost 1-hop by 20", "1-hop connections by 20 points"
    graph_match = re.search(r"(\d+)[- ]?hop\S*\s+.*?(?:by|boost|\+)\s*(\d+)", text)
    if not graph_match:
        # alternate: "boost ... 1-hop ... +20"
        graph_match = re.search(r"(?:boost|proximity)\s+(\d+)[- ]?hop\S*\s*.*?(\d+)", text)
    if graph_match:
        rules.append(Rule(
            rule_type="graph_proximity_boost",
            hops=int(graph_match.group(1)),
            risk_boost=float(graph_match.group(2)),
            description=f"Add +{graph_match.group(2)} to graph score for {graph_match.group(1)}-hop connections",
        ))

    # threshold change: "adjust threshold to 0.65", "set threshold 0.5"
    thresh_match = re.search(r"threshold\s*(?:to|=|at)?\s*(0\.\d+)", text)
    if thresh_match:
        rules.append(Rule(
            rule_type="threshold_change",
            value=float(thresh_match.group(1)),
            description=f"Adjust decision threshold to {thresh_match.group(1)}",
        ))

    # weight adjustments: "increase raw weight", "decrease ml weight"
    weight_match = re.search(r"(increase|decrease)\s+(\w+)\s+weight", text)
    if weight_match:
        rules.append(Rule(
            rule_type="weight_adjustment",
            description=f"{weight_match.group(1).capitalize()} {weight_match.group(2).upper()} weight",
            extra={"direction": weight_match.group(1), "layer": weight_match.group(2)},
        ))

    # focus area: "focus on crypto transactions", "prioritize UPI fraud"
    focus_match = re.search(r"(?:focus\s+on|prioritize)\s+(.+?)(?:\.|$)", text)
    if focus_match and not recall_match:
        rules.append(Rule(
            rule_type="focus_area",
            description=f"Focus analysis on: {focus_match.group(1).strip()}",
            extra={"area": focus_match.group(1).strip()},
        ))

    # generic fallback — if triggers match but no specific rule parsed
    if not rules and detect_rules(user_text):
        rules.append(Rule(
            rule_type="custom",
            description=user_text.strip()[:200],
        ))

    return rules


# ── 2b) Natural-Language → Structured Compliance Rule ────────────────────────

_NL_RULE_PARSE_PROMPT = (
    "You are a compliance rule parser for the AEGIS-AML system.\n"
    "The user will describe a transaction monitoring rule in plain English.\n"
    "Parse it into a JSON object with EXACTLY these keys:\n"
    '  "name": short rule title (max 8 words),\n'
    '  "description": one sentence describing what the rule detects,\n'
    '  "conditions": array of human-readable condition strings '
    '(e.g. ["Amount > 50000", "Sender_bank_location ≠ Receiver_bank_location"]),\n'
    '  "severity": one of "High", "Medium", or "Low",\n'
    '  "parameters": object of extracted thresholds/values '
    '(e.g. {"amount_threshold": 50000, "time_window_hours": 24})\n\n'
    "Field reference (available columns): Time, Date, Sender_account, "
    "Receiver_account, Amount, Payment_currency, Received_currency, "
    "Sender_bank_location, Receiver_bank_location, Payment_type, "
    "Is_laundering, Laundering_type.\n\n"
    "Return ONLY the JSON object, no markdown, no explanation.\n\n"
    "User rule description: "
)


def parse_nl_rule_to_structured(user_text: str) -> Dict[str, Any]:
    """Parse natural-language rule text into a structured compliance rule dict.

    Returns dict with keys: name, description, conditions, severity, parameters.
    On failure, includes an 'error' key with a message.
    """
    if not user_text or not user_text.strip():
        return {"error": "Empty rule text provided."}

    result = _parse_nl_rule_via_llm(user_text.strip())
    if result and not result.get("error"):
        return result

    # Fallback to heuristic extraction
    return _parse_nl_rule_heuristic(user_text.strip())


def _parse_nl_rule_via_llm(user_text: str) -> Dict[str, Any]:
    """Call local Ollama to parse a natural-language rule into structured form."""
    llm_enabled = _is_llm_enabled()
    if not llm_enabled:
        return {"error": "LLM unavailable/disabled. Using heuristic fallback."}

    endpoint = os.getenv("AEGIS_LLM_ENDPOINT", "http://localhost:11434/api/generate")
    model = os.getenv("AEGIS_LLM_MODEL", "phi3.5")

    payload = {
        "model": model,
        "prompt": _NL_RULE_PARSE_PROMPT + user_text,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 512},
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

        raw = body.get("response", "{}")
        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            return {"error": "LLM returned non-object response."}

        # Validate required fields
        name = str(parsed.get("name", "")).strip()
        description = str(parsed.get("description", "")).strip()
        conditions = parsed.get("conditions", [])
        severity = str(parsed.get("severity", "Medium")).strip()
        parameters = parsed.get("parameters", {})

        if not name:
            name = "Custom NL Rule"
        if not description:
            description = user_text[:120]
        if not isinstance(conditions, list) or not conditions:
            conditions = [user_text[:200]]
        if severity not in ("High", "Medium", "Low"):
            severity = "Medium"
        if not isinstance(parameters, dict):
            parameters = {}

        return {
            "name": name,
            "description": description,
            "conditions": [str(c) for c in conditions],
            "severity": severity,
            "parameters": parameters,
            "source": "llm",
        }

    except (error.URLError, TimeoutError, OSError) as exc:
        return {"error": f"LLM connection failed: {exc}. Using heuristic fallback."}
    except (ValueError, json.JSONDecodeError) as exc:
        return {"error": f"LLM output parse error: {exc}. Using heuristic fallback."}


def _parse_nl_rule_heuristic(user_text: str) -> Dict[str, Any]:
    """Regex-based fallback: extract rule structure from plain English."""
    text = user_text.lower()
    conditions: list[str] = []
    parameters: Dict[str, Any] = {}
    severity = "Medium"

    # Amount thresholds: "amount > 10000", "amount greater than $50k"
    amt_match = re.search(
        r"amount\s*(?:>|>=|greater\s+than|over|above|exceeds?)\s*\$?([\d,]+\.?\d*)\s*([kmb])?",
        text,
    )
    if amt_match:
        raw_val = float(amt_match.group(1).replace(",", ""))
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(
            amt_match.group(2) or "", 1
        )
        threshold = raw_val * multiplier
        conditions.append(f"Amount > {threshold:,.0f}")
        parameters["amount_threshold"] = threshold
        if threshold >= 50_000:
            severity = "High"

    # Cross-border / location mismatch
    if re.search(r"cross[- ]?border|different\s+countr|location\s*(?:!=|≠|mismatch|differ)", text):
        conditions.append("Sender_bank_location ≠ Receiver_bank_location")

    # Currency mismatch
    if re.search(r"currency\s*(?:!=|≠|mismatch|differ)|different\s+currenc", text):
        conditions.append("Payment_currency ≠ Received_currency")

    # Payment type filters
    pt_match = re.search(r"payment[_ ]?type\s*(?:=|is|in)\s*['\"]?(\w[\w\s,-]+)", text)
    if pt_match:
        conditions.append(f"Payment_type = '{pt_match.group(1).strip()}'")

    # Frequency / velocity rules
    freq_match = re.search(r"more\s+than\s+(\d+)\s+(?:transfer|transaction|payment)s?\s+(?:in|within|per)\s+(?:the\s+)?(?:last\s+)?(\d+)\s*(hour|minute|day|h|m|d)", text)
    if freq_match:
        count = int(freq_match.group(1))
        window = int(freq_match.group(2))
        unit = freq_match.group(3)[0]
        unit_label = {"h": "hour", "m": "minute", "d": "day"}[unit]
        conditions.append(f"Transaction frequency > {count} per {window} {unit_label}(s)")
        parameters["frequency_threshold"] = count
        parameters["time_window"] = f"{window}{unit}"

    # Risk boost
    boost_match = re.search(r"boost\s+(?:risk\s+)?(?:score\s+)?(?:by\s+)?(\d+)", text)
    if boost_match:
        parameters["risk_boost"] = int(boost_match.group(1))

    # Jurisdiction / country
    jurisdiction_match = re.search(r"(?:jurisdiction|country|region|location)\s+(?:is\s+)?(?:not\s+)?(?:in\s+)?(?:our\s+)?(?:white|black|sanction)\s*list", text)
    if jurisdiction_match:
        conditions.append("Receiver_bank_location NOT IN whitelist")
        severity = "High"

    # If nothing was extracted, use the raw text as a condition
    if not conditions:
        conditions = [user_text.strip()[:200]]

    # Infer severity from keywords
    if re.search(r"\b(critical|highest|extreme|immediate)\b", text):
        severity = "High"
    elif re.search(r"\b(low|minor|informational)\b", text):
        severity = "Low"

    # Build name from first condition or first few words
    name_words = user_text.strip().split()[:6]
    name = " ".join(name_words)
    if len(name) > 50:
        name = name[:47] + "…"

    return {
        "name": name.title(),
        "description": user_text.strip()[:200],
        "conditions": conditions,
        "severity": severity,
        "parameters": parameters,
        "source": "heuristic",
    }


# ── 3) Prompt Injection ─────────────────────────────────────────────────────


def apply_rules_to_prompt(rules: List[Rule], prompt: str) -> str:
    """Prefix *prompt* with active session rules so the LLM considers them.

    Inserts rules in a human-readable block at the top of the prompt.
    """
    if not rules:
        return prompt

    lines = [
        "=== ACTIVE SESSION RULES (you MUST consider these) ===",
    ]
    for idx, rule in enumerate(rules, 1):
        parts = [f"Rule {idx}: [{rule.rule_type}] {rule.description}"]
        if rule.value is not None:
            parts.append(f"  target_value={rule.value}")
        if rule.hops is not None:
            parts.append(f"  hops={rule.hops}")
        if rule.risk_boost is not None:
            parts.append(f"  risk_boost={rule.risk_boost}")
        if rule.extra:
            parts.append(f"  extra={json.dumps(rule.extra)}")
        lines.append("\n".join(parts))
    lines.append("=== END SESSION RULES ===\n")

    return "\n".join(lines) + "\n" + prompt


# ── 4) Structured LLM Output Format ─────────────────────────────────────────

STRUCTURED_OUTPUT_INSTRUCTION = (
    "IMPORTANT: Structure your response using EXACTLY these three sections:\n\n"
    "[PLAN]\n"
    "(Your detailed reasoning steps, considering all active session rules)\n\n"
    "[RESULT]\n"
    "(Your answer based on artifacts, data, and session rules)\n\n"
    "[SUGGESTED NEXT]\n"
    "(List of 2-4 suggested follow-up prompts the user could try)\n"
)


def format_llm_response(raw_response: str) -> Dict[str, str]:
    """Parse an LLM response into [PLAN], [RESULT], [SUGGESTED NEXT] sections.

    Returns dict with keys 'plan', 'result', 'suggested_next'.
    Falls back to putting entire response in 'result' if sections not found.
    """
    sections: Dict[str, str] = {"plan": "", "result": "", "suggested_next": ""}

    plan_match = re.search(r"\[PLAN\]\s*\n(.*?)(?=\[RESULT\]|\[SUGGESTED|\Z)", raw_response, re.DOTALL)
    result_match = re.search(r"\[RESULT\]\s*\n(.*?)(?=\[SUGGESTED|\Z)", raw_response, re.DOTALL)
    suggested_match = re.search(r"\[SUGGESTED\s*NEXT\]\s*\n(.*?)$", raw_response, re.DOTALL)

    if plan_match:
        sections["plan"] = plan_match.group(1).strip()
    if result_match:
        sections["result"] = result_match.group(1).strip()
    if suggested_match:
        sections["suggested_next"] = suggested_match.group(1).strip()

    # Fallback: entire response goes into result
    if not any(sections.values()):
        sections["result"] = raw_response.strip()

    return sections


# ── 5) Session Persistence ───────────────────────────────────────────────────


class SessionRuleStore:
    """Thread-safe, JSON-file-backed session rule persistence.

    Storage location: data/session_rules/<session_id>.json
    """

    def __init__(self, session_id: str = "default") -> None:
        self._session_id = session_id
        self._lock = Lock()
        _PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _PERSISTENCE_DIR / f"{session_id}.json"
        self._rules: List[Rule] = self._load()

    def _load(self) -> List[Rule]:
        """Load rules from JSON file on disk."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                return [Rule.from_dict(item) for item in data if isinstance(item, dict)]
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def _persist(self) -> None:
        """Write current rules to disk."""
        self._path.write_text(
            json.dumps([r.to_dict() for r in self._rules], indent=2),
            encoding="utf-8",
        )

    def add_rules(self, new_rules: List[Rule]) -> List[Rule]:
        """Add rules and persist. Returns full list of active rules."""
        with self._lock:
            self._rules.extend(new_rules)
            self._persist()
            return list(self._rules)

    def get_rules(self) -> List[Rule]:
        """Return snapshot of active session rules."""
        with self._lock:
            return list(self._rules)

    def clear(self) -> None:
        """Remove all session rules."""
        with self._lock:
            self._rules.clear()
            self._persist()

    def remove_rule(self, index: int) -> bool:
        """Remove a rule by 0-based index. Returns True on success."""
        with self._lock:
            if 0 <= index < len(self._rules):
                self._rules.pop(index)
                self._persist()
                return True
            return False


# ── 6) Chat-Oriented LLM Call (ties everything together) ────────────────────


def chat_with_rules(
    user_message: str,
    session_rules: List[Rule],
    system_context: str = "",
    ml_artifacts: str = "",
) -> str:
    """Send a chat message to local Ollama with session rules injected.

    Falls back to a structured non-LLM response when Ollama is unavailable.
    """
    # Build composite prompt
    prompt_parts: list[str] = []

    if system_context:
        prompt_parts.append(system_context)

    if ml_artifacts:
        prompt_parts.append(f"=== ML ARTIFACTS ===\n{ml_artifacts}\n=== END ML ARTIFACTS ===\n")

    # Inject session rules
    rules_prefix = apply_rules_to_prompt(session_rules, "")
    if rules_prefix.strip():
        prompt_parts.append(rules_prefix)

    # Add structured output instruction
    prompt_parts.append(STRUCTURED_OUTPUT_INSTRUCTION)

    # Add user message
    prompt_parts.append(f"User: {user_message}")

    full_prompt = "\n\n".join(prompt_parts)

    # Try LLM when explicitly enabled
    llm_enabled = _is_llm_enabled()
    if llm_enabled:
        response = _call_ollama(full_prompt)
        if response:
            return response

    # Fallback: generate a structured non-LLM response
    return _generate_fallback_response(user_message, session_rules)


def _call_ollama(prompt: str) -> Optional[str]:
    """Low-level Ollama API call."""
    endpoint = os.getenv("AEGIS_LLM_ENDPOINT", "http://localhost:11434/api/generate")
    model = os.getenv("AEGIS_LLM_MODEL", "phi3.5")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": LLM_NUM_PREDICT},
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
        return body.get("response", "").strip() or None
    except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        return None


def _generate_fallback_response(user_message: str, rules: List[Rule]) -> str:
    """Structured fallback when Ollama is unreachable."""
    rules_summary = ""
    if rules:
        rules_summary = "\n".join(
            f"  - [{r.rule_type}] {r.description}" for r in rules
        )
    else:
        rules_summary = "  (no session rules active)"

    return (
        "[PLAN]\n"
        f"Analyzing user query: \"{user_message[:120]}\"\n"
        f"Active session rules considered:\n{rules_summary}\n"
        "LLM is currently unavailable (disabled, unreachable, or timed out) — providing rule-aware heuristic response.\n\n"
        "[RESULT]\n"
        "The AEGIS-AML system received your query. "
        "Session rules are stored and will be applied to all subsequent LLM-powered analysis. "
        "Check that Ollama is running and reachable at localhost:11434; "
        "if you explicitly disabled LLM, set AEGIS_LLM_ENABLED=true to re-enable it.\n\n"
        "[SUGGESTED NEXT]\n"
        "- Run a Live Detection to see rules in action\n"
        "- Type 'show rules' to list active session rules\n"
        "- Type 'clear rules' to reset all session rules\n"
        "- Ask about a specific account or transaction pattern\n"
    )
