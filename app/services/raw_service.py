from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List

from app.core.config import CONFIG
from app.schemas.scam_exposure import ScamExposureRequest


SANCTIONED_IDENTIFIERS = {"bad_actor@upi", "sanctioned_acct_01"}
RAW_RULES_PATH = Path("rules/raw_rules.json")


@dataclass
class RawRiskResult:
    score: float
    reasoning: List[str]
    contributions: Dict[str, float]


@dataclass(frozen=True)
class RuleComponentConfig:
    id: str
    description: str
    component_type: str
    weight: float
    params: Dict[str, float | int | str]


@dataclass(frozen=True)
class RuleConfig:
    rule_id: str
    name: str
    priority: str
    components: List[RuleComponentConfig]


@dataclass(frozen=True)
class RawRuleSet:
    top_k: int
    cap: float
    note_terms: List[str]
    rules: List[RuleConfig]


_RULESET_CACHE: RawRuleSet | None = None
_RULESET_MTIME: float | None = None


DEFAULT_NOTE_TERMS = [
    "mule",
    "cashout",
    "urgent",
    "crypto",
    "giftcard",
    "untraceable",
    "bypass",
]


def evaluate_raw_risk(payload: ScamExposureRequest) -> RawRiskResult:
    reasons: List[str] = []
    contributions: Dict[str, float] = {}
    rule_scores: List[tuple[str, str, float, List[str]]] = []

    ruleset = _get_ruleset()
    note_hits = _count_note_hits(payload.transaction_note, ruleset.note_terms)

    for rule in ruleset.rules:
        matched_components: List[str] = []
        score = 0.0
        for component in rule.components:
            if _evaluate_component(component, payload, note_hits):
                score += component.weight
                matched_components.append(component.description)

        bounded_rule_score = min(1.0, round(score, 4))
        if bounded_rule_score > 0:
            rule_scores.append((rule.rule_id, rule.name, bounded_rule_score, matched_components))

    if not rule_scores:
        return RawRiskResult(
            score=0.0,
            reasoning=["No deterministic RAW guardrail triggered."],
            contributions={},
        )

    top_rules = sorted(rule_scores, key=lambda item: item[2], reverse=True)[: ruleset.top_k]
    combined = min(ruleset.cap, sum(item[2] for item in top_rules))
    bounded_score = round(min(CONFIG.max_score, combined * CONFIG.max_score), 2)

    for rule_id, rule_name, rule_score, matched_components in top_rules:
        contribution = round(rule_score * CONFIG.max_score, 2)
        contributions[f"{rule_id}:{rule_name}"] = contribution
        reasons.append(
            f"{rule_id} {rule_name} triggered ({contribution}/100): " + "; ".join(matched_components)
        )

    return RawRiskResult(score=bounded_score, reasoning=reasons, contributions=contributions)


def _get_ruleset() -> RawRuleSet:
    global _RULESET_CACHE, _RULESET_MTIME

    try:
        mtime = RAW_RULES_PATH.stat().st_mtime
    except FileNotFoundError:
        return _default_ruleset()

    if _RULESET_CACHE is not None and _RULESET_MTIME == mtime:
        return _RULESET_CACHE

    try:
        payload = json.loads(RAW_RULES_PATH.read_text(encoding="utf-8"))
        rules = [_parse_rule(rule_payload) for rule_payload in payload.get("rules", [])]
        aggregation = payload.get("aggregation", {})
        top_k = int(aggregation.get("top_k", 3))
        cap = float(aggregation.get("cap", 1.0))
        note_terms = [
            str(term).strip().lower()
            for term in payload.get("note_terms", DEFAULT_NOTE_TERMS)
            if str(term).strip()
        ]

        parsed = RawRuleSet(
            top_k=max(1, top_k),
            cap=max(0.1, min(1.0, cap)),
            note_terms=note_terms,
            rules=rules,
        )
        _RULESET_CACHE = parsed
        _RULESET_MTIME = mtime
        return parsed
    except (ValueError, TypeError, json.JSONDecodeError):
        return _default_ruleset()


def _parse_rule(payload: dict) -> RuleConfig:
    components: List[RuleComponentConfig] = []
    for item in payload.get("components", []):
        components.append(
            RuleComponentConfig(
                id=str(item.get("id", "component")),
                description=str(item.get("description", "rule component matched")),
                component_type=str(item.get("type", "")),
                weight=float(item.get("weight", 0.0)),
                params=item.get("params", {}),
            )
        )

    return RuleConfig(
        rule_id=str(payload.get("rule_id", "R000")),
        name=str(payload.get("name", "UnnamedRule")),
        priority=str(payload.get("priority", "medium")),
        components=components,
    )


def _evaluate_component(component: RuleComponentConfig, payload: ScamExposureRequest, note_hits: int) -> bool:
    params = component.params
    component_type = component.component_type

    if component_type == "watchlist_upi":
        return bool(payload.upi_id and payload.upi_id.lower() in SANCTIONED_IDENTIFIERS)
    if component_type == "velocity_gt":
        return payload.tx_count_last_hour > int(params.get("threshold", CONFIG.velocity_threshold_per_hour))
    if component_type == "velocity_gte":
        return payload.tx_count_last_hour >= int(params.get("threshold", CONFIG.velocity_threshold_per_hour))
    if component_type == "amount_gte":
        return payload.transaction_amount >= float(params.get("threshold", CONFIG.high_amount_threshold))
    if component_type == "amount_round_multiple":
        multiple = float(params.get("multiple", 1000))
        return payload.transaction_amount > 0 and multiple > 0 and payload.transaction_amount % multiple == 0
    if component_type == "amount_round_and_velocity":
        multiple = float(params.get("multiple", 1000))
        velocity_threshold = int(params.get("velocity_threshold", 4))
        is_round = payload.transaction_amount > 0 and multiple > 0 and payload.transaction_amount % multiple == 0
        return is_round and payload.tx_count_last_hour >= velocity_threshold
    if component_type == "upi_missing":
        return payload.upi_id is None
    if component_type == "upi_missing_and_amount_gte":
        threshold = float(params.get("threshold", CONFIG.high_amount_threshold * 0.75))
        return payload.upi_id is None and payload.transaction_amount >= threshold
    if component_type == "note_terms_gte":
        min_hits = int(params.get("min_hits", 1))
        return note_hits >= min_hits

    return False


def _count_note_hits(note: str | None, terms: List[str]) -> int:
    if not note:
        return 0
    lowered = note.lower()
    return sum(1 for term in terms if term in lowered)


def _default_ruleset() -> RawRuleSet:
    rules = [
        RuleConfig(
            rule_id="R001",
            name="Sanctions_Identifier_Hit",
            priority="high",
            components=[
                RuleComponentConfig(
                    id="c1",
                    description="UPI/account matched watchlist",
                    component_type="watchlist_upi",
                    weight=1.0,
                    params={},
                )
            ],
        ),
        RuleConfig(
            rule_id="R002",
            name="Velocity_HighTx_1h",
            priority="high",
            components=[
                RuleComponentConfig(
                    id="c1",
                    description="Sender transaction count breached 1h threshold",
                    component_type="velocity_gt",
                    weight=0.7,
                    params={"threshold": CONFIG.velocity_threshold_per_hour},
                ),
                RuleComponentConfig(
                    id="c2",
                    description="Very high 1h velocity",
                    component_type="velocity_gte",
                    weight=0.3,
                    params={"threshold": CONFIG.velocity_threshold_per_hour + 4},
                ),
            ],
        ),
        RuleConfig(
            rule_id="R003",
            name="HighValue_SingleTxn",
            priority="medium",
            components=[
                RuleComponentConfig(
                    id="c1",
                    description="Amount crossed high-value threshold",
                    component_type="amount_gte",
                    weight=0.7,
                    params={"threshold": CONFIG.high_amount_threshold},
                ),
                RuleComponentConfig(
                    id="c2",
                    description="Amount is extreme high-value",
                    component_type="amount_gte",
                    weight=0.3,
                    params={"threshold": CONFIG.high_amount_threshold * 2.5},
                ),
            ],
        ),
    ]
    return RawRuleSet(top_k=3, cap=1.0, note_terms=DEFAULT_NOTE_TERMS, rules=rules)
