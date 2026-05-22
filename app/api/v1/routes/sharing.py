"""Sharing API — exposes the trained ML model and local LLM for remote teammates.

Endpoints
---------
POST /api/v1/ml/predict          — standalone ML inference (XGBoost or proxy)
GET  /api/v1/ml/info             — model metadata + SHAP top features
POST /api/v1/llm/chat            — conversational LLM (Ollama) with session rules
POST /api/v1/nlp/analyze         — NLP note risk scoring (lexicon + LLM)
GET  /api/v1/llm/status          — LLM connectivity check
GET  /api/v1/session-rules       — list active session rules
POST /api/v1/session-rules       — inject rules via natural language
DELETE /api/v1/session-rules     — clear all session rules
GET  /api/v1/llm/chat-history    — list assistant chat history
DELETE /api/v1/llm/chat-history  — clear assistant chat history
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from urllib import error, request

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.security import require_api_key
from app.schemas.sharing import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    InjectRulesRequest,
    InjectRulesResponse,
    LLMChatRequest,
    LLMChatResponse,
    LLMStatusResponse,
    MLInferenceRequest,
    MLInferenceResponse,
    MLTrainInlineRequest,
    MLTrainRequest,
    MLTrainResponse,
    ModelInfoResponse,
    NLPAnalyzeRequest,
    NLPAnalyzeResponse,
    RuleOut,
    SessionRulesResponse,
)
from app.services.chat_history import ChatHistoryStore
from app.services.nlp_service import analyze_note_risk, set_session_rules
from app.services.session_rules import (
    SessionRuleStore,
    chat_with_rules,
    detect_rules,
    format_llm_response,
    parse_rules,
)

router = APIRouter(prefix="/api/v1", tags=["sharing"])

# ── Singletons ───────────────────────────────────────────────────────────────

_MODEL_PATH = Path("artifacts/ml_model.joblib")
_METADATA_PATH = Path("artifacts/ml_model_metadata.json")
_SHAP_PATH = Path("artifacts/ml_model_shap_summary.json")
_DEFAULT_TRAINING_PATH = Path("data/training_transactions.csv")
_MAX_INLINE_CSV_CHARS = 6_000_000

_rule_store_cache: dict[str, SessionRuleStore] = {}
_chat_store_cache: dict[str, ChatHistoryStore] = {}
_cache_lock = Lock()


def _is_llm_enabled() -> bool:
    raw = os.getenv("CRYPT_ML_LLM_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _rule_to_out(r) -> RuleOut:
    d = r.to_dict()
    return RuleOut(
        rule_type=d["rule_type"],
        description=d["description"],
        parameters=d.get("parameters", {}),
        created_at=d.get("created_at", ""),
    )


def _session_id_for_dataset(dataset_id: Optional[str]) -> str:
    if dataset_id is None or not str(dataset_id).strip():
        return "api"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(dataset_id).strip())
    normalized = normalized.strip("_") or "dataset"
    return f"api_{normalized}"


def _get_rule_store(dataset_id: Optional[str]) -> SessionRuleStore:
    session_id = _session_id_for_dataset(dataset_id)
    with _cache_lock:
        store = _rule_store_cache.get(session_id)
        if store is None:
            store = SessionRuleStore(session_id=session_id)
            _rule_store_cache[session_id] = store
        return store


def _get_chat_store(dataset_id: Optional[str]) -> ChatHistoryStore:
    session_id = _session_id_for_dataset(dataset_id)
    with _cache_lock:
        store = _chat_store_cache.get(session_id)
        if store is None:
            store = ChatHistoryStore(session_id=session_id)
            _chat_store_cache[session_id] = store
        return store


def _load_model_info_payload() -> tuple[Optional[Dict], Optional[List[Dict]]]:
    metadata: Optional[Dict] = None
    shap_top: Optional[List[Dict]] = None

    if _METADATA_PATH.exists():
        try:
            metadata = json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            metadata = None

    if _SHAP_PATH.exists():
        try:
            shap_data = json.loads(_SHAP_PATH.read_text(encoding="utf-8"))
            shap_top = shap_data.get("top_features", [])[:15]
        except (json.JSONDecodeError, OSError):
            shap_top = None

    return metadata, shap_top


# ── ML Inference ─────────────────────────────────────────────────────────────


@router.post("/ml/predict", response_model=MLInferenceResponse)
def ml_predict(
    payload: MLInferenceRequest,
    _: None = Depends(require_api_key),
) -> MLInferenceResponse:
    """Run the trained ML model (or deterministic proxy) on AML-CFT payload.

    This is the standalone inference endpoint — it does NOT run the full
    3-layer orchestration (use ``/scam-exposure`` for that).

    Accepts AML-CFT upload-schema fields and maps them to internal model
    features (transaction_amount, tx_count_last_hour, has_upi, nlp_signal).
    """
    from app.services.ml_service import _load_model, evaluate_ml_risk
    from app.core.config import CONFIG
    from app.schemas.scam_exposure import ScamExposureRequest

    # ── Map AML-CFT fields → internal model features ────────────
    transaction_amount = float(payload.Amount)
    has_sender = bool(payload.Sender_account and payload.Sender_account.strip())

    # Cross-currency / cross-border risk signals → nlp_signal component
    pay_curr = payload.Payment_currency.strip().lower()
    recv_curr = payload.Received_currency.strip().lower()
    sender_loc = payload.Sender_bank_location.strip().lower()
    receiver_loc = payload.Receiver_bank_location.strip().lower()
    payment_type = payload.Payment_type.strip().lower()
    laundering_type = payload.Laundering_type.strip().lower()

    payment_type_risk = {
        "cross-border": 30.0, "cash deposit": 18.0, "cheque": 12.0,
        "ach": 10.0, "credit card": 8.0, "debit card": 6.0, "wire": 15.0,
    }.get(payment_type, 5.0)
    cross_currency_risk = 20.0 if pay_curr != recv_curr else 0.0
    cross_border_risk = 22.0 if sender_loc != receiver_loc else 0.0
    import re
    laundering_text_risk = 18.0 if re.search(
        r"fan_out|fan.in|fan_in|group|layer|cross", laundering_type
    ) else 0.0
    derived_nlp_signal = min(
        payment_type_risk + cross_currency_risk + cross_border_risk + laundering_text_risk, 100.0
    )

    # NLP analysis on the note (if provided) — blended with derived signal
    nlp_result = analyze_note_risk(payload.transaction_note)
    final_nlp = max(derived_nlp_signal, nlp_result.score)

    # tx_count_last_hour is not available in a single-row API call;
    # estimate as 1 (caller can extend payload if needed)
    tx_count_last_hour = 1

    model = _load_model()

    if model is not None:
        features = pd.DataFrame(
            [
                {
                    "transaction_amount": transaction_amount,
                    "tx_count_last_hour": float(tx_count_last_hour),
                    "has_upi": float(1 if has_sender else 0),
                    "nlp_signal": float(final_nlp),
                }
            ]
        )
        probability = float(model.predict_proba(features)[0][1])
        score = round(probability * CONFIG.max_score, 2)

        contributions = {
            "transaction_amount": round(min(transaction_amount / 150_000.0, 1.0) * 35.0, 2),
            "velocity_signal": round(min(tx_count_last_hour / 12.0, 1.0) * 35.0, 2),
            "nlp_signal": round(min(final_nlp / 100.0, 1.0) * 20.0, 2),
            "account_presence": round((1.0 if has_sender else 0.3) * 10.0, 2),
        }
        reasoning = [
            "Score from trained XGBoost model (artifacts/ml_model.joblib).",
            "AML-CFT fields mapped to model features; NLP signal derived from payment/currency/location.",
        ]
        source = "trained_model"
    else:
        velocity = min(tx_count_last_hour / 10.0, 1.0)
        amount = min(transaction_amount / 100_000.0, 1.0)
        novelty = 0.35 if not has_sender else 0.1
        nlp_comp = min(final_nlp / 100.0, 1.0)

        probability = 0.35 * velocity + 0.35 * amount + 0.15 * novelty + 0.15 * nlp_comp
        score = round(probability * CONFIG.max_score, 2)

        contributions = {
            "velocity_signal": round(velocity * 35.0, 2),
            "amount_signal": round(amount * 35.0, 2),
            "novelty_signal": round(novelty * 15.0, 2),
            "nlp_signal": round(nlp_comp * 15.0, 2),
        }
        reasoning = [
            "No trained model found — deterministic proxy scoring used.",
        ]
        source = "deterministic_proxy"

    if nlp_result.matched_terms:
        reasoning.append(f"NLP terms matched: {', '.join(nlp_result.matched_terms)}")

    return MLInferenceResponse(
        score=score,
        probability=round(probability, 6),
        contributions=contributions,
        reasoning=reasoning,
        model_source=source,
        nlp_terms=nlp_result.matched_terms,
        nlp_summary=nlp_result.llm_summary,
    )


@router.get("/ml/info", response_model=ModelInfoResponse)
def ml_info(
    _: None = Depends(require_api_key),
) -> ModelInfoResponse:
    """Return model artifact metadata and top SHAP features."""
    metadata, shap_top = _load_model_info_payload()

    return ModelInfoResponse(
        model_available=_MODEL_PATH.exists(),
        model_path=str(_MODEL_PATH),
        metadata=metadata,
        shap_top_features=shap_top,
    )


@router.post("/ml/train", response_model=MLTrainResponse)
def ml_train(
    payload: MLTrainRequest,
    _: None = Depends(require_api_key),
) -> MLTrainResponse:
    """Train or retrain the local XGBoost model from a server-side CSV path."""
    from app.services.ml_service import _load_model
    from scripts.train_ml import train_model

    data_path = Path(payload.data_path).expanduser()
    if not data_path.exists():
        raise HTTPException(status_code=404, detail=f"Training CSV not found at {data_path}")

    try:
        train_model(data_path=data_path, target_recall=float(payload.target_recall))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}") from exc

    _load_model.cache_clear()
    metadata, shap_top = _load_model_info_payload()

    return MLTrainResponse(
        status="trained",
        message=f"Model retrained from {data_path}",
        model_available=_MODEL_PATH.exists(),
        model_path=str(_MODEL_PATH),
        metadata=metadata,
        shap_top_features=shap_top,
    )


@router.post("/ml/train-inline", response_model=MLTrainResponse)
def ml_train_inline(
    payload: MLTrainInlineRequest,
    _: None = Depends(require_api_key),
) -> MLTrainResponse:
    """Train or retrain the local model from inline CSV content sent by UI."""
    from app.services.ml_service import _load_model
    from scripts.train_ml import train_model

    csv_content = str(payload.csv_content or "")
    if len(csv_content) > _MAX_INLINE_CSV_CHARS:
        raise HTTPException(
            status_code=413,
            detail=(
                "Uploaded CSV content is too large for inline training payload. "
                "Use /api/v1/ml/train with a server-side data path instead."
            ),
        )

    _DEFAULT_TRAINING_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_TRAINING_PATH.write_text(csv_content, encoding="utf-8")

    try:
        train_model(data_path=_DEFAULT_TRAINING_PATH, target_recall=float(payload.target_recall))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}") from exc

    _load_model.cache_clear()
    metadata, shap_top = _load_model_info_payload()

    return MLTrainResponse(
        status="trained",
        message=f"Model retrained from inline CSV ({payload.source_name})",
        model_available=_MODEL_PATH.exists(),
        model_path=str(_MODEL_PATH),
        metadata=metadata,
        shap_top_features=shap_top,
    )


# ── LLM Chat ────────────────────────────────────────────────────────────────


def _get_ml_artifacts_summary() -> str:
    """Compact ML artifact summary for LLM context injection."""
    parts: list[str] = []
    if _METADATA_PATH.exists():
        try:
            meta = json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
            parts.append(
                f"Model: rows={meta.get('rows_used')}, "
                f"ROC-AUC={meta.get('roc_auc')}, "
                f"threshold={meta.get('threshold')}, "
                f"features={meta.get('feature_count', 'n/a')}"
            )
        except (json.JSONDecodeError, OSError):
            pass
    if _SHAP_PATH.exists():
        try:
            shap = json.loads(_SHAP_PATH.read_text(encoding="utf-8"))
            top = shap.get("top_features", [])[:5]
            if top:
                feat_str = ", ".join(f"{f['feature']}={f.get('importance', 'n/a')}" for f in top)
                parts.append(f"Top SHAP: {feat_str}")
        except (json.JSONDecodeError, OSError):
            pass
    return "\n".join(parts) if parts else "No ML artifacts available."


@router.post("/llm/chat", response_model=LLMChatResponse)
def llm_chat(
    payload: LLMChatRequest,
    _: None = Depends(require_api_key),
) -> LLMChatResponse:
    """Send a message to the crypt.ml LLM assistant.

    Session rules from the API rule store are automatically injected.
    Supports natural-language rule injection (same as the dashboard AI Chat).
    """
    user_msg = payload.message.strip()
    dataset_id = payload.dataset_id
    rule_store = _get_rule_store(dataset_id)

    # Check for rule injection in the message
    if detect_rules(user_msg):
        new_rules = parse_rules(user_msg)
        if new_rules:
            all_rules = rule_store.add_rules(new_rules)
            set_session_rules(all_rules)

    active_rules = rule_store.get_rules()
    set_session_rules(active_rules)

    system_ctx = payload.system_context or (
        "You are the crypt.ml AI assistant. You help analyse anti-money-laundering "
        "transactions, explain risk scores, discuss SHAP features, and recommend actions. "
        "You MUST honour all active session rules in your reasoning."
    )

    ml_artifacts = _get_ml_artifacts_summary() if payload.include_ml_artifacts else ""

    raw_response = chat_with_rules(
        user_message=user_msg,
        session_rules=active_rules,
        system_context=system_ctx,
        ml_artifacts=ml_artifacts,
    )

    sections = format_llm_response(raw_response)

    if payload.store_in_history:
        chat_store = _get_chat_store(dataset_id)
        chat_store.add(role="user", text=user_msg)
        chat_store.add(role="assistant", text=sections.get("result") or raw_response)

    llm_enabled = _is_llm_enabled()
    model_name = os.getenv("CRYPT_ML_LLM_MODEL", "phi3.5") if llm_enabled else "fallback"

    return LLMChatResponse(
        reply=raw_response,
        plan=sections.get("plan"),
        result=sections.get("result"),
        suggested_next=sections.get("suggested_next"),
        llm_used=llm_enabled,
        model_name=model_name,
    )


@router.get("/llm/status", response_model=LLMStatusResponse)
def llm_status(
    _: None = Depends(require_api_key),
) -> LLMStatusResponse:
    """Check LLM (Ollama) connectivity and configuration."""
    llm_enabled = _is_llm_enabled()
    endpoint = os.getenv("CRYPT_ML_LLM_ENDPOINT", "http://localhost:11434/api/generate")
    model_name = os.getenv("CRYPT_ML_LLM_MODEL", "phi3.5")

    # Quick connectivity probe
    ollama_reachable = False
    try:
        # Ollama exposes a lightweight tag list endpoint
        base_url = endpoint.rsplit("/api/", 1)[0]
        req = request.Request(f"{base_url}/api/tags", method="GET")
        with request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                ollama_reachable = True
    except Exception:
        pass

    return LLMStatusResponse(
        llm_enabled=llm_enabled,
        model_name=model_name,
        endpoint=endpoint,
        ollama_reachable=ollama_reachable,
    )


# ── NLP Analysis ─────────────────────────────────────────────────────────────


@router.post("/nlp/analyze", response_model=NLPAnalyzeResponse)
def nlp_analyze(
    payload: NLPAnalyzeRequest,
    _: None = Depends(require_api_key),
) -> NLPAnalyzeResponse:
    """Analyse a transaction note for AML risk signals (lexicon + optional LLM)."""
    result = analyze_note_risk(payload.note)
    llm_enabled = _is_llm_enabled()

    return NLPAnalyzeResponse(
        score=result.score,
        matched_terms=result.matched_terms,
        llm_summary=result.llm_summary,
        llm_enabled=llm_enabled,
    )


# ── Session Rules CRUD ──────────────────────────────────────────────────────


@router.get("/session-rules", response_model=SessionRulesResponse)
def list_session_rules(
    dataset_id: Optional[str] = None,
    _: None = Depends(require_api_key),
) -> SessionRulesResponse:
    """List all active API session rules."""
    session_id = _session_id_for_dataset(dataset_id)
    rules = _get_rule_store(dataset_id).get_rules()
    return SessionRulesResponse(
        session_id=session_id,
        dataset_id=dataset_id,
        rules=[_rule_to_out(r) for r in rules],
        count=len(rules),
    )


@router.post("/session-rules", response_model=InjectRulesResponse)
def inject_session_rules(
    payload: InjectRulesRequest,
    _: None = Depends(require_api_key),
) -> InjectRulesResponse:
    """Inject session rules from a natural-language instruction.

    Example body: ``{"text": "In this session, prioritize recall >= 0.80"}``
    """
    rule_store = _get_rule_store(payload.dataset_id)
    new_rules = parse_rules(payload.text)
    if not new_rules:
        return InjectRulesResponse(injected=[], total_active=len(rule_store.get_rules()))

    all_rules = rule_store.add_rules(new_rules)
    set_session_rules(all_rules)

    return InjectRulesResponse(
        injected=[_rule_to_out(r) for r in new_rules],
        total_active=len(all_rules),
    )


@router.delete("/session-rules")
def clear_session_rules(
    dataset_id: Optional[str] = None,
    _: None = Depends(require_api_key),
) -> dict:
    """Clear all API session rules."""
    _get_rule_store(dataset_id).clear()
    set_session_rules([])
    return {
        "status": "cleared",
        "rules_remaining": 0,
        "session_id": _session_id_for_dataset(dataset_id),
    }


@router.get("/llm/chat-history", response_model=ChatHistoryResponse)
def list_chat_history(
    dataset_id: Optional[str] = None,
    limit: int = 80,
    _: None = Depends(require_api_key),
) -> ChatHistoryResponse:
    """List chat history for a dataset-scoped (or global) assistant session."""
    safe_limit = max(1, min(limit, 200))
    session_id = _session_id_for_dataset(dataset_id)
    messages = _get_chat_store(dataset_id).list(limit=safe_limit)
    return ChatHistoryResponse(
        session_id=session_id,
        dataset_id=dataset_id,
        messages=[
            ChatHistoryMessage(role=item.role, text=item.text, created_at=item.created_at)
            for item in messages
        ],
        count=len(messages),
    )


@router.delete("/llm/chat-history")
def clear_chat_history(
    dataset_id: Optional[str] = None,
    _: None = Depends(require_api_key),
) -> dict:
    """Clear chat history for a dataset-scoped (or global) assistant session."""
    removed = _get_chat_store(dataset_id).clear()
    return {
        "status": "cleared",
        "removed": removed,
        "session_id": _session_id_for_dataset(dataset_id),
    }
