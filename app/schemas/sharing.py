"""Pydantic schemas for the Model & LLM sharing API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── ML Inference ─────────────────────────────────────────────────────────────


class MLInferenceRequest(BaseModel):
    """Standalone ML model inference — accepts AML-CFT upload-schema fields.

    The API maps these to internal model features (transaction_amount,
    tx_count_last_hour, has_upi, nlp_signal) automatically.
    """

    Amount: float = Field(ge=0.0, description="Transaction amount")
    Sender_account: str = Field(description="Sender account identifier")
    Receiver_account: str = Field(default="", description="Receiver account identifier")
    Payment_currency: str = Field(default="INR", description="Payment currency code")
    Received_currency: str = Field(default="INR", description="Received currency code")
    Sender_bank_location: str = Field(default="IN", description="Sender bank country")
    Receiver_bank_location: str = Field(default="IN", description="Receiver bank country")
    Payment_type: str = Field(default="ACH", description="Payment type (Cross-border, Cash deposit, etc.)")
    Laundering_type: str = Field(default="", description="Laundering type hint (optional)")
    transaction_note: Optional[str] = Field(
        default=None,
        description="Free-text note for NLP risk augmentation",
    )


class MLInferenceResponse(BaseModel):
    score: float = Field(description="Risk score 0-100")
    probability: float = Field(description="Raw model probability (0-1)")
    contributions: Dict[str, float] = Field(description="Per-feature contribution breakdown")
    reasoning: List[str] = Field(description="Explainability trace")
    model_source: str = Field(description="'trained_model' or 'deterministic_proxy'")
    nlp_terms: List[str] = Field(default_factory=list, description="NLP-matched risk terms")
    nlp_summary: Optional[str] = Field(default=None, description="LLM NLP summary if available")


class ModelInfoResponse(BaseModel):
    model_available: bool
    model_path: str
    metadata: Optional[Dict] = None
    shap_top_features: Optional[List[Dict]] = None


# ── LLM Chat ────────────────────────────────────────────────────────────────


class LLMChatRequest(BaseModel):
    """Send a message to the AEGIS-AML LLM assistant via API."""

    message: str = Field(..., min_length=1, max_length=2000, description="User message / question")
    system_context: Optional[str] = Field(
        default=None,
        description="Optional system context override. Defaults to AML assistant prompt.",
    )
    include_ml_artifacts: bool = Field(
        default=True,
        description="Include current ML model metadata/SHAP in LLM context",
    )


class LLMChatResponse(BaseModel):
    reply: str = Field(description="Full LLM response text")
    plan: Optional[str] = Field(default=None, description="[PLAN] reasoning section")
    result: Optional[str] = Field(default=None, description="[RESULT] answer section")
    suggested_next: Optional[str] = Field(default=None, description="[SUGGESTED NEXT] follow-ups")
    llm_used: bool = Field(description="True if Ollama was used; False if fallback")
    model_name: str = Field(description="Ollama model name or 'fallback'")


# ── NLP Analysis ─────────────────────────────────────────────────────────────


class NLPAnalyzeRequest(BaseModel):
    """Analyse a transaction note for AML risk signals."""

    note: str = Field(..., min_length=1, max_length=5000, description="Transaction note text")


class NLPAnalyzeResponse(BaseModel):
    score: float = Field(description="Blended NLP risk score 0-100")
    matched_terms: List[str]
    llm_summary: Optional[str] = None
    llm_enabled: bool = Field(description="Whether LLM was active for this call")


# ── Session Rules (API-level CRUD) ───────────────────────────────────────────


class RuleOut(BaseModel):
    rule_type: str
    description: str
    parameters: Dict
    created_at: str


class SessionRulesResponse(BaseModel):
    session_id: str
    rules: List[RuleOut]
    count: int


class InjectRulesRequest(BaseModel):
    """Natural-language text that may contain one or more session rules."""

    text: str = Field(..., min_length=1, max_length=2000)


class InjectRulesResponse(BaseModel):
    injected: List[RuleOut]
    total_active: int


class LLMStatusResponse(BaseModel):
    llm_enabled: bool
    model_name: str
    endpoint: str
    ollama_reachable: bool
