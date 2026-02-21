from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict, List

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.scam_exposure import FeedbackRequest, ScamExposureRequest
from app.services.session_rules import (
    Rule,
    SessionRuleStore,
    chat_with_rules,
    detect_rules,
    format_llm_response,
    parse_nl_rule_to_structured,
    parse_rules,
)
from app.services.nlp_service import set_session_rules

# Heavy imports are lazy-loaded inside the tabs that need them to keep startup fast.
# - scripts.train_ml (xgboost + shap ~4s) → Training Control tab only
# - app.services.data_generator (~0.6s)   → Data Generator tab only
# - app.services.orchestrator (~1.3s)     → deferred to first actual use via cache

DATA_PATH = PROJECT_ROOT / "data" / "training_transactions.csv"
MODEL_PATH = PROJECT_ROOT / "artifacts" / "ml_model.joblib"
METADATA_PATH = PROJECT_ROOT / "artifacts" / "ml_model_metadata.json"
SHAP_PATH = PROJECT_ROOT / "artifacts" / "ml_model_shap_summary.json"


@st.cache_resource
def get_orchestrator():
    """Lazy-import orchestrator (pulls xgboost via ml_service) only on first use."""
    from app.services.orchestrator import RiskOrchestrator
    return RiskOrchestrator()


@st.cache_resource
def get_rule_store() -> SessionRuleStore:
    """Singleton session rule store — persists across Streamlit reruns."""
    return SessionRuleStore(session_id="dashboard")


def render_page_style() -> None:
    st.set_page_config(page_title="AEGIS-AML Hackathon Command Center", page_icon="🛡️", layout="wide")
    st.markdown(
        """
        <style>
            .block-container {padding-top: 1rem; padding-bottom: 1rem;}
            .hero {
                border-radius: 14px;
                padding: 1rem 1.2rem;
                background: linear-gradient(140deg, #0f172a, #1d4ed8 60%, #0ea5e9);
                color: #f8fafc;
                margin-bottom: 1rem;
            }
            .card {
                border-radius: 12px;
                border: 1px solid rgba(120,120,120,0.20);
                padding: 0.75rem 0.9rem;
                background: rgba(255,255,255,0.02);
            }
            /* Dataset card grid */
            .ds-card {
                border-radius: 14px;
                border: 1px solid rgba(120,120,120,0.22);
                padding: 1.05rem 1.1rem;
                background: rgba(255,255,255,0.02);
                transition: box-shadow 0.2s, border-color 0.2s, transform 0.2s;
                height: 100%;
                min-height: 280px;
                position: relative;
                overflow: hidden;
            }
            .ds-card:hover {
                border-color: #3b82f6;
                box-shadow: 0 8px 22px rgba(59,130,246,0.14);
                transform: translateY(-1px);
            }
            .ds-card h4 { margin: 0 0 0.35rem 0; font-size: 1.03rem; line-height: 1.3; }
            .ds-card .ds-meta { color: #94a3b8; font-size: 0.8rem; margin-bottom: 0.55rem; }
            .ds-card-topbar {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 3px;
                background: rgba(120,120,120,0.2);
            }
            .ds-card-topbar.inprogress {
                background: linear-gradient(90deg, rgba(59,130,246,0.45), rgba(59,130,246,0.95));
            }
            .ds-card-topbar.completed {
                background: linear-gradient(90deg, rgba(16,185,129,0.35), rgba(16,185,129,0.7));
            }
            .ds-card-topbar.pending {
                background: linear-gradient(90deg, rgba(245,158,11,0.35), rgba(245,158,11,0.75));
            }
            .ds-header-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.7rem;
            }
            .ds-status-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.23rem 0.65rem;
                border-radius: 999px;
                font-size: 0.7rem;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
                border: 1px solid transparent;
            }
            .ds-status-pill.completed {
                background: rgba(16,185,129,0.15);
                color: #10b981;
                border-color: rgba(16,185,129,0.3);
            }
            .ds-status-pill.inprogress {
                background: rgba(59,130,246,0.14);
                color: #60a5fa;
                border-color: rgba(59,130,246,0.35);
            }
            .ds-status-pill.pending {
                background: rgba(245,158,11,0.14);
                color: #f59e0b;
                border-color: rgba(245,158,11,0.35);
            }
            .ds-status-dot {
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: currentColor;
            }
            .ds-risk-row, .ds-tx-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-top: 1px solid rgba(120,120,120,0.14);
                padding: 0.52rem 0;
                font-size: 0.82rem;
            }
            .ds-label { color: #94a3b8; font-weight: 600; }
            .ds-value { color: #e2e8f0; font-weight: 700; }
            .ds-badge {
                display: inline-block;
                padding: 2px 9px;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 600;
                margin-right: 4px;
            }
            .ds-badge-high   { background: #fecaca; color: #991b1b; }
            .ds-badge-medium { background: #fef08a; color: #854d0e; }
            .ds-badge-low    { background: #bbf7d0; color: #166534; }
            .ds-badge-unknown{ background: #e2e8f0; color: #475569; }
            .ds-badge-pending     { background: #e0e7ff; color: #3730a3; }
            .ds-badge-inprogress  { background: #fef3c7; color: #92400e; }
            .ds-badge-completed   { background: #d1fae5; color: #065f46; }
            .ds-add-card {
                border: 2px dashed rgba(120,120,120,0.32);
                border-radius: 14px;
                padding: 2.1rem 1rem;
                text-align: center;
                color: #94a3b8;
                transition: border-color 0.2s, background 0.2s;
                height: 100%;
                min-height: 280px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background: rgba(255,255,255,0.01);
            }
            .ds-add-icon {
                width: 56px;
                height: 56px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(59,130,246,0.1);
                color: #60a5fa;
                font-size: 1.75rem;
                margin-bottom: 0.6rem;
            }
            .ds-add-card:hover {
                border-color: #3b82f6;
                color: #3b82f6;
                background: rgba(59,130,246,0.05);
            }
            .ds-stat { font-size: 0.85rem; color: #cbd5e1; }

            /* Step wizard bar */
            .step-bar {
                display: flex;
                gap: 0;
                margin-bottom: 1.2rem;
            }
            .step-item {
                flex: 1;
                text-align: center;
                padding: 0.65rem 0.5rem;
                font-size: 0.85rem;
                font-weight: 600;
                border-bottom: 3px solid rgba(120,120,120,0.2);
                color: #64748b;
                transition: all 0.2s;
            }
            .step-item.active {
                border-bottom-color: #3b82f6;
                color: #3b82f6;
            }
            .step-item.done {
                border-bottom-color: #22c55e;
                color: #22c55e;
            }

            /* Validation check cards */
            .vcheck-card {
                border-radius: 10px;
                border: 1px solid rgba(120,120,120,0.2);
                padding: 0.9rem 1rem;
                background: rgba(255,255,255,0.02);
                margin-bottom: 0.6rem;
                transition: border-color 0.2s;
            }
            .vcheck-card.pass { border-left: 4px solid #22c55e; }
            .vcheck-card.fail { border-left: 4px solid #ef4444; }
            .vcheck-card.warn { border-left: 4px solid #f59e0b; }
            .vcheck-card .vcheck-title {
                font-weight: 600;
                font-size: 0.92rem;
                margin-bottom: 0.2rem;
            }
            .vcheck-card .vcheck-detail {
                font-size: 0.82rem;
                color: #94a3b8;
            }

            /* Rule cards */
            .rule-card {
                border-radius: 10px;
                border: 1px solid rgba(120,120,120,0.25);
                padding: 0.9rem 1.1rem;
                background: rgba(255,255,255,0.03);
                transition: box-shadow 0.2s, border-color 0.2s;
                margin-bottom: 0.6rem;
            }
            .rule-card:hover {
                border-color: #3b82f6;
                box-shadow: 0 2px 12px rgba(59,130,246,0.1);
            }
            .rule-card .rule-name {
                font-weight: 600;
                font-size: 0.95rem;
                margin-bottom: 0.2rem;
            }
            .rule-card .rule-id {
                font-size: 0.75rem;
                color: #64748b;
                font-family: monospace;
            }
            .rule-card .rule-desc {
                font-size: 0.83rem;
                color: #94a3b8;
                margin-top: 0.35rem;
            }

            /* Summary info card */
            .info-card {
                border-radius: 12px;
                border: 1px solid rgba(120,120,120,0.2);
                padding: 1rem 1.2rem;
                background: rgba(255,255,255,0.03);
            }
            .info-card h5 { margin: 0 0 0.6rem 0; font-size: 0.95rem; }
            .info-row {
                display: flex;
                justify-content: space-between;
                padding: 0.3rem 0;
                border-bottom: 1px solid rgba(120,120,120,0.08);
                font-size: 0.85rem;
            }
            .info-row .info-label { color: #94a3b8; }
            .info-row .info-value { font-weight: 600; }

            /* ── Natural Language Rule Builder ────────────────── */
            .nl-builder {
                border: 1px solid rgba(120,120,120,0.25);
                border-radius: 14px;
                padding: 1.2rem 1.3rem;
                background: rgba(255,255,255,0.02);
                margin-top: 0.6rem;
            }
            .nl-builder-header {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.7rem;
            }
            .nl-builder-header h4 {
                margin: 0;
                font-size: 1rem;
            }
            .nl-builder-tip {
                font-size: 0.78rem;
                color: #64748b;
                background: rgba(59,130,246,0.08);
                border-radius: 8px;
                padding: 0.45rem 0.75rem;
                margin-bottom: 0.8rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }
            .nl-confirm-card {
                border: 1px solid rgba(34,197,94,0.35);
                border-left: 4px solid #22c55e;
                border-radius: 10px;
                padding: 1rem 1.2rem;
                background: rgba(34,197,94,0.04);
                margin-top: 0.8rem;
            }
            .nl-confirm-card h5 { margin: 0 0 0.5rem 0; font-size: 0.95rem; }
            .nl-confirm-card .nl-cond-item {
                font-size: 0.82rem;
                color: #cbd5e1;
                padding: 2px 0;
            }
            .nl-confirm-card .nl-params {
                font-size: 0.78rem;
                color: #64748b;
                margin-top: 0.4rem;
                font-family: monospace;
            }
            .nl-error-card {
                border: 1px solid rgba(239,68,68,0.35);
                border-left: 4px solid #ef4444;
                border-radius: 10px;
                padding: 0.9rem 1.1rem;
                background: rgba(239,68,68,0.04);
                margin-top: 0.8rem;
            }
            .nl-error-card .nl-error-text {
                font-size: 0.85rem;
                color: #f87171;
            }
            .nl-source-badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: 0.7rem;
                font-weight: 600;
            }
            .nl-source-llm {
                background: #dbeafe;
                color: #1e40af;
            }
            .nl-source-heuristic {
                background: #fef3c7;
                color: #92400e;
            }

            /* ── Data Query Assistant ────────────────────── */
            .dqa-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.6rem;
            }
            .dqa-header-left {
                display: flex;
                align-items: center;
                gap: 0.65rem;
            }
            .dqa-header-left h3 { margin: 0; }
            .dqa-header-right {
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            .dqa-status-dot {
                display: inline-block;
                width: 8px; height: 8px;
                border-radius: 50%;
                margin-right: 4px;
            }
            .dqa-status-dot.online  { background: #22c55e; }
            .dqa-status-dot.offline { background: #ef4444; }

            /* Chat area */
            .dqa-chat-container {
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 14px;
                padding: 0;
                background: rgba(255,255,255,0.01);
                min-height: 480px;
            }
            .dqa-greeting {
                text-align: center;
                padding: 2.5rem 1.5rem 1rem;
            }
            .dqa-greeting h4 { margin: 0 0 0.4rem 0; font-size: 1.1rem; }
            .dqa-greeting p  { color: #94a3b8; font-size: 0.88rem; margin: 0; }
            .dqa-suggestions {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 0.55rem;
                margin-top: 1.2rem;
                padding: 0 1rem;
            }
            .dqa-suggest-btn {
                border: 1px solid rgba(120,120,120,0.25);
                border-radius: 10px;
                padding: 0.65rem 0.85rem;
                background: rgba(255,255,255,0.02);
                cursor: pointer;
                transition: border-color 0.2s, box-shadow 0.2s;
                text-align: left;
            }
            .dqa-suggest-btn:hover {
                border-color: #3b82f6;
                box-shadow: 0 2px 10px rgba(59,130,246,0.12);
            }
            .dqa-suggest-btn .dqa-sicon {
                font-size: 1rem;
                margin-bottom: 0.15rem;
            }
            .dqa-suggest-btn .dqa-slabel {
                font-size: 0.82rem;
                font-weight: 600;
                margin-bottom: 0.1rem;
            }
            .dqa-suggest-btn .dqa-sdesc {
                font-size: 0.73rem;
                color: #94a3b8;
            }

            /* Context insights sidebar */
            .dqa-insight-panel {
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 14px;
                padding: 1rem 1.1rem;
                background: rgba(255,255,255,0.02);
                margin-bottom: 0.8rem;
            }
            .dqa-insight-panel h5 {
                margin: 0 0 0.6rem 0;
                font-size: 0.92rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }

            /* Risk meter gauge */
            .dqa-risk-meter {
                text-align: center;
                padding: 0.8rem 0 0.4rem;
            }
            .dqa-risk-meter .dqa-meter-ring {
                position: relative;
                display: inline-block;
                width: 110px; height: 110px;
            }
            .dqa-risk-meter .dqa-meter-ring svg {
                transform: rotate(-90deg);
            }
            .dqa-meter-value {
                position: absolute;
                top: 50%; left: 50%;
                transform: translate(-50%, -50%);
                font-size: 1.4rem;
                font-weight: 700;
            }
            .dqa-meter-label {
                font-size: 0.78rem;
                color: #94a3b8;
                margin-top: 0.25rem;
            }
            .dqa-meter-sublabel {
                font-size: 0.7rem;
                color: #64748b;
            }

            /* Entity badges */
            .dqa-entity-item {
                display: flex;
                align-items: center;
                gap: 0.55rem;
                padding: 0.45rem 0;
                border-bottom: 1px solid rgba(120,120,120,0.08);
            }
            .dqa-entity-item:last-child { border-bottom: none; }
            .dqa-entity-avatar {
                width: 32px; height: 32px;
                border-radius: 8px;
                display: flex; align-items: center; justify-content: center;
                font-size: 0.85rem;
                font-weight: 700;
                flex-shrink: 0;
            }
            .dqa-entity-info {
                flex: 1;
                min-width: 0;
            }
            .dqa-entity-name {
                font-size: 0.82rem;
                font-weight: 600;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .dqa-entity-meta {
                font-size: 0.7rem;
                color: #94a3b8;
            }
            .dqa-entity-score {
                font-size: 0.78rem;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 8px;
                flex-shrink: 0;
            }
            .dqa-entity-score.high   { background: #fecaca; color: #991b1b; }
            .dqa-entity-score.medium { background: #fef08a; color: #854d0e; }
            .dqa-entity-score.low    { background: #bbf7d0; color: #166534; }

            /* Action cards */
            .dqa-action-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 0.65rem;
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 10px;
                margin-bottom: 0.45rem;
                cursor: pointer;
                transition: border-color 0.2s, background 0.2s;
            }
            .dqa-action-item:hover {
                border-color: #3b82f6;
                background: rgba(59,130,246,0.04);
            }
            .dqa-action-icon {
                font-size: 1.05rem;
                flex-shrink: 0;
            }
            .dqa-action-text {
                font-size: 0.82rem;
                font-weight: 500;
            }
            .dqa-action-badge {
                margin-left: auto;
                font-size: 0.68rem;
                padding: 2px 7px;
                border-radius: 999px;
                font-weight: 600;
            }
            .dqa-action-badge.priority {
                background: #fecaca;
                color: #991b1b;
            }
            .dqa-action-badge.normal {
                background: #dbeafe;
                color: #1e40af;
            }
            .dqa-action-badge.info {
                background: #e0e7ff;
                color: #3730a3;
            }

            /* Chat history toolbar */
            .dqa-toolbar {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.35rem;
            }
            .dqa-toolbar-btn {
                display: inline-flex;
                align-items: center;
                gap: 0.3rem;
                padding: 0.3rem 0.65rem;
                border: 1px solid rgba(120,120,120,0.25);
                border-radius: 8px;
                font-size: 0.78rem;
                color: #94a3b8;
                cursor: pointer;
                transition: border-color 0.2s, color 0.2s;
                background: transparent;
            }
            .dqa-toolbar-btn:hover {
                border-color: #3b82f6;
                color: #3b82f6;
            }
            .dqa-thinking {
                font-size: 0.78rem;
                color: #64748b;
                background: rgba(59,130,246,0.06);
                border-radius: 8px;
                padding: 0.5rem 0.75rem;
                margin-bottom: 0.5rem;
                border-left: 3px solid #3b82f6;
            }
            .dqa-follow-chip {
                display: inline-block;
                padding: 0.3rem 0.7rem;
                border: 1px solid rgba(120,120,120,0.25);
                border-radius: 999px;
                font-size: 0.78rem;
                margin: 0.2rem 0.2rem 0 0;
                cursor: pointer;
                transition: border-color 0.2s, background 0.2s;
            }
            .dqa-follow-chip:hover {
                border-color: #3b82f6;
                background: rgba(59,130,246,0.06);
            }

            /* ── Risk Analysis Dashboard ─────────────────── */
            .ra-session-timeline {
                display: flex;
                align-items: center;
                gap: 0;
                margin-bottom: 1rem;
            }
            .ra-tl-step {
                display: flex;
                align-items: center;
                gap: 0.35rem;
                font-size: 0.78rem;
                color: #64748b;
                padding: 0.3rem 0.7rem;
                border-radius: 999px;
                border: 1px solid rgba(120,120,120,0.2);
                transition: all 0.2s;
            }
            .ra-tl-step.done {
                background: rgba(34,197,94,0.08);
                border-color: #22c55e;
                color: #22c55e;
            }
            .ra-tl-step.active {
                background: rgba(59,130,246,0.10);
                border-color: #3b82f6;
                color: #3b82f6;
                font-weight: 600;
            }
            .ra-tl-arrow {
                color: #475569;
                margin: 0 0.25rem;
                font-size: 0.7rem;
            }

            /* Summary metric cards */
            .ra-metric-card {
                border-radius: 12px;
                border: 1px solid rgba(120,120,120,0.2);
                padding: 1rem 1.1rem;
                background: rgba(255,255,255,0.02);
                transition: border-color 0.2s, box-shadow 0.2s;
            }
            .ra-metric-card:hover {
                border-color: #3b82f6;
                box-shadow: 0 2px 12px rgba(59,130,246,0.1);
            }
            .ra-metric-label {
                font-size: 0.78rem;
                color: #94a3b8;
                margin-bottom: 0.25rem;
            }
            .ra-metric-value {
                font-size: 1.6rem;
                font-weight: 700;
                line-height: 1.1;
            }
            .ra-metric-trend {
                font-size: 0.75rem;
                margin-top: 0.2rem;
            }
            .ra-metric-trend.up   { color: #ef4444; }
            .ra-metric-trend.down { color: #22c55e; }
            .ra-metric-trend.flat { color: #94a3b8; }

            /* Risk distribution chip/tag */
            .ra-risk-tag {
                display: inline-block;
                padding: 2px 10px;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 600;
            }
            .ra-risk-tag.high   { background: #fecaca; color: #991b1b; }
            .ra-risk-tag.medium { background: #fef08a; color: #854d0e; }
            .ra-risk-tag.low    { background: #bbf7d0; color: #166534; }

            /* Entity analysis card */
            .ra-entity-card {
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 14px;
                padding: 1.1rem 1.2rem;
                background: rgba(255,255,255,0.02);
            }
            .ra-entity-card h5 {
                margin: 0 0 0.6rem 0;
                font-size: 0.95rem;
            }
            .ra-violation-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.4rem 0;
                border-bottom: 1px solid rgba(120,120,120,0.08);
                font-size: 0.82rem;
            }
            .ra-violation-row:last-child { border-bottom: none; }
            .ra-violation-label { color: #cbd5e1; }
            .ra-violation-pts {
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 0.75rem;
            }
            .ra-violation-pts.high   { background: #fecaca; color: #991b1b; }
            .ra-violation-pts.medium { background: #fef08a; color: #854d0e; }
            .ra-violation-pts.low    { background: #bbf7d0; color: #166534; }

            /* Action cards */
            .ra-action-card {
                display: flex;
                align-items: center;
                gap: 0.55rem;
                padding: 0.55rem 0.75rem;
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 10px;
                margin-bottom: 0.4rem;
                transition: border-color 0.2s, background 0.2s;
                cursor: pointer;
            }
            .ra-action-card:hover {
                border-color: #3b82f6;
                background: rgba(59,130,246,0.04);
            }
            .ra-action-icon { font-size: 1.05rem; flex-shrink: 0; }
            .ra-action-text { font-size: 0.82rem; flex: 1; }
            .ra-action-priority {
                font-size: 0.68rem;
                padding: 2px 7px;
                border-radius: 999px;
                font-weight: 600;
            }
            .ra-action-priority.urgent { background: #fecaca; color: #991b1b; }
            .ra-action-priority.rec    { background: #dbeafe; color: #1e40af; }
            .ra-action-priority.info   { background: #e0e7ff; color: #3730a3; }

            /* LLM insight panel */
            .ra-llm-panel {
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 14px;
                padding: 1rem 1.2rem;
                background: rgba(255,255,255,0.02);
                border-left: 4px solid #8b5cf6;
            }
            .ra-llm-panel h5 {
                margin: 0 0 0.5rem 0;
                font-size: 0.92rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }
            .ra-llm-insight {
                font-size: 0.85rem;
                color: #cbd5e1;
                line-height: 1.5;
            }
            .ra-prompt-chip {
                display: inline-block;
                padding: 0.35rem 0.75rem;
                border: 1px solid rgba(120,120,120,0.25);
                border-radius: 999px;
                font-size: 0.78rem;
                margin: 0.25rem 0.25rem 0 0;
                cursor: pointer;
                transition: border-color 0.2s, background 0.2s;
            }
            .ra-prompt-chip:hover {
                border-color: #8b5cf6;
                background: rgba(139,92,246,0.06);
            }

            /* Risk panel card wrapper */
            .ra-panel {
                border: 1px solid rgba(120,120,120,0.2);
                border-radius: 14px;
                padding: 1rem 1.2rem;
                background: rgba(255,255,255,0.02);
                margin-bottom: 0.8rem;
            }
            .ra-panel h5 {
                margin: 0 0 0.6rem 0;
                font-size: 0.92rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hero">
          <h2 style="margin:0;">AEGIS-AML — Hackathon Command Center</h2>
          <p style="margin:0.35rem 0 0 0;">Live AML scoring, human feedback calibration, model training, and explainability in one UI.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_status(orchestrator: RiskOrchestrator, rule_store: SessionRuleStore) -> None:
    st.sidebar.header("System Status")
    weights = orchestrator.get_weights().weights
    st.sidebar.metric("RAW Weight", f"{weights.raw:.4f}")
    st.sidebar.metric("ML Weight", f"{weights.ml:.4f}")
    st.sidebar.metric("GRAPH Weight", f"{weights.graph:.4f}")

    if METADATA_PATH.exists():
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        st.sidebar.success("Model artifact detected")
        st.sidebar.caption(f"Rows: {metadata.get('rows_used', 'n/a')}")
        st.sidebar.caption(f"ROC-AUC: {metadata.get('roc_auc', 'n/a')}")
        st.sidebar.caption(f"Threshold: {metadata.get('threshold', 'n/a')}")
    else:
        st.sidebar.warning("No model metadata found")

    # ── Active Session Rules ─────────────────────
    active_rules = rule_store.get_rules()
    st.sidebar.divider()
    st.sidebar.header(f"Session Rules ({len(active_rules)})")
    if active_rules:
        for idx, rule in enumerate(active_rules):
            st.sidebar.markdown(
                f"**{idx + 1}.** `{rule.rule_type}`  \n{rule.description}"
            )
        if st.sidebar.button("Clear All Rules", key="sidebar_clear_rules"):
            rule_store.clear()
            set_session_rules([])
            st.rerun()
    else:
        st.sidebar.caption("No rules active. Configure them in Datasets → Compliance Rules.")


def section_live_detection(orchestrator: RiskOrchestrator) -> None:
    st.subheader("Live Transaction Detection")

    left, right = st.columns([1, 1.35], gap="large")
    with left:
        with st.form("live_tx_form"):
            account_id = st.text_input("Account ID", value="acct_1001")
            upi_id = st.text_input("UPI ID (optional)", value="user@upi")
            amount = st.number_input("Transaction Amount", min_value=0.0, value=62000.0, step=500.0)
            tx_count = st.number_input("Transactions in Last Hour", min_value=0, value=7, step=1)
            note = st.text_area("Transaction Note (optional)", value="urgent cashout to mule wallet", height=100)
            submitted = st.form_submit_button("Run Risk Analysis", use_container_width=True, type="primary")

        if submitted:
            payload = ScamExposureRequest(
                account_id=account_id.strip(),
                upi_id=upi_id.strip() or None,
                transaction_amount=float(amount),
                tx_count_last_hour=int(tx_count),
                transaction_note=note.strip() or None,
            )
            st.session_state["last_result"] = orchestrator.process(payload)

    with right:
        result = st.session_state.get("last_result")
        if result is None:
            st.info("Submit transaction input to see live AML scoring.")
            return

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Risk Score", f"{result.risk_score:.2f}/100")
        m2.metric("Trust Score", f"{result.trust_score:.2f}/10")
        m3.metric("Exposure", result.exposure_level)
        m4.metric("Case ID", result.case_id[:8])

        st.markdown(f"**Summary:** {result.summary}")

        layer_df = pd.DataFrame(
            [
                {"layer": "RAW", "score": result.risk_breakdown["raw"].score},
                {"layer": "ML", "score": result.risk_breakdown["ml"].score},
                {"layer": "GRAPH", "score": result.risk_breakdown["graph"].score},
            ]
        )
        st.bar_chart(layer_df.set_index("layer"))

        st.markdown("**Orchestration Trace**")
        trace_df = pd.DataFrame([step.model_dump() for step in result.orchestrator_trace])
        st.dataframe(trace_df, use_container_width=True)

        with st.expander("Layer Explanations", expanded=False):
            for layer_name in ("raw", "ml", "graph"):
                layer = result.risk_breakdown[layer_name]
                st.markdown(f"**{layer_name.upper()}** — score `{layer.score:.2f}`")
                for reason in layer.reasoning:
                    st.write(f"- {reason}")
                if layer.contributions:
                    contrib_df = pd.DataFrame(
                        [{"signal": key, "value": value} for key, value in layer.contributions.items()]
                    )
                    st.dataframe(contrib_df, use_container_width=True)


def section_feedback_loop(orchestrator: RiskOrchestrator) -> None:
    st.subheader("Human Feedback Calibration")

    result = st.session_state.get("last_result")
    default_case = result.case_id if result is not None else ""

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        case_id = st.text_input("Case ID", value=default_case)
        outcome = st.selectbox("Analyst Outcome", ["confirmed_fraud", "false_positive", "needs_review"])
        notes = st.text_area("Analyst Notes", value="", height=100)

        if st.button("Apply Feedback", type="primary", use_container_width=True):
            response = orchestrator.apply_feedback(FeedbackRequest(case_id=case_id, outcome=outcome, notes=notes or None))
            st.session_state["last_feedback"] = response

    with col2:
        feedback = st.session_state.get("last_feedback")
        weights = orchestrator.get_weights().weights
        st.metric("RAW", f"{weights.raw:.4f}")
        st.metric("ML", f"{weights.ml:.4f}")
        st.metric("GRAPH", f"{weights.graph:.4f}")

        if feedback is not None:
            st.success(f"Feedback status: {feedback.status}")
            st.write(feedback.message)
            st.json(feedback.model_dump())


def section_batch_simulation(orchestrator: RiskOrchestrator) -> None:
    st.subheader("Batch Simulation Lab")

    batch_count = st.slider("Number of synthetic transactions", min_value=10, max_value=300, value=80, step=10)
    suspicious_ratio = st.slider("Suspicious scenario ratio", min_value=0.05, max_value=0.80, value=0.30, step=0.05)

    if st.button("Run Batch Simulation", use_container_width=True):
        records: List[Dict] = []
        suspicious_cut = int(batch_count * suspicious_ratio)

        for idx in range(batch_count):
            suspicious = idx < suspicious_cut
            records.append(
                {
                    "account_id": f"acct_{1000 + idx}",
                    "upi_id": "bad_actor@upi" if suspicious and idx % 7 == 0 else f"user{idx}@upi",
                    "transaction_amount": 85000.0 if suspicious else 3500.0,
                    "tx_count_last_hour": 9 if suspicious else 1,
                    "transaction_note": "urgent mule ring cross-border" if suspicious else "regular transfer",
                }
            )

        outcomes = []
        for row in records:
            res = orchestrator.process(ScamExposureRequest(**row))
            outcomes.append({"exposure": res.exposure_level, "score": res.risk_score})

        outcomes_df = pd.DataFrame(outcomes)
        st.session_state["batch_outcomes"] = outcomes_df

    outcomes_df = st.session_state.get("batch_outcomes")
    if outcomes_df is None:
        st.info("Run a batch simulation to inspect decision distributions.")
        return

    counts = outcomes_df["exposure"].value_counts().rename_axis("exposure").reset_index(name="count")
    st.bar_chart(counts.set_index("exposure"))
    st.dataframe(outcomes_df.describe(), use_container_width=True)


@st.cache_data(show_spinner="Loading training data (sampled)...")
def _load_training_preview(csv_path: str, _mtime: float):
    """Load training CSV with sampling for large files. Cached by path+mtime."""
    from scripts.train_ml import to_model_schema, split_features
    import os

    file_size = os.path.getsize(csv_path)
    # For files > 50 MB, sample to avoid freezing the dashboard
    if file_size > 50 * 1024 * 1024:
        # Read just the header + a sample
        raw_df_full = pd.read_csv(csv_path, nrows=0)  # header only
        total_rows = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1
        # Read a 10k-row sample for preview
        raw_df = pd.read_csv(csv_path, nrows=10_000)
    else:
        raw_df = pd.read_csv(csv_path)
        total_rows = len(raw_df)

    mapped_df = to_model_schema(raw_df)
    features, target = split_features(mapped_df)
    return {
        "total_rows": total_rows,
        "sampled_rows": len(raw_df),
        "mapped_rows": len(mapped_df),
        "label_dist": target.value_counts().to_dict(),
        "features_head": features.head(10),
        "is_sampled": total_rows != len(raw_df),
    }


def section_training_control() -> None:
    st.subheader("No-Code Training Control")

    upload_col, action_col = st.columns([1.3, 1], gap="large")
    with upload_col:
        uploaded = st.file_uploader("Upload training CSV", type=["csv"], key="training_upload")
        if uploaded is not None:
            DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            DATA_PATH.write_bytes(uploaded.getbuffer())
            st.success(f"Saved uploaded dataset to {DATA_PATH}")

        if not DATA_PATH.exists():
            st.warning("Upload a CSV or place file at data/training_transactions.csv")
            return

        try:
            mtime = DATA_PATH.stat().st_mtime
            info = _load_training_preview(str(DATA_PATH), mtime)

            if info["is_sampled"]:
                st.info(f"Large dataset detected — showing preview of {info['sampled_rows']:,} rows out of {info['total_rows']:,} total.")
            st.write(f"Total rows: {info['total_rows']:,} | Transformed (sample): {info['mapped_rows']:,}")
            st.write(f"Label distribution (sample): {info['label_dist']}")
            st.dataframe(info["features_head"], use_container_width=True)
        except Exception as exc:
            st.error(f"Error loading training data preview: {exc}")

    with action_col:
        target_recall = st.slider("Target Recall", min_value=0.50, max_value=0.95, value=0.70, step=0.01)
        if st.button("Train Model", type="primary", use_container_width=True):
            with st.spinner("Training model... this may take time for large datasets"):
                try:
                    from scripts.train_ml import train_model
                    train_model(DATA_PATH, target_recall=target_recall)
                    st.success("Training completed. Artifacts refreshed.")
                except Exception as exc:
                    st.error(f"Training failed: {exc}")

        if METADATA_PATH.exists():
            st.markdown("**Latest Metadata**")
            st.json(json.loads(METADATA_PATH.read_text(encoding="utf-8")))


def section_explainability() -> None:
    st.subheader("Model Explainability & Artifacts")

    left, right = st.columns([1, 1], gap="large")
    with left:
        if METADATA_PATH.exists():
            metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
            st.markdown("**Training Metadata**")
            st.json(metadata)
        else:
            st.info("No metadata file found yet.")

    with right:
        if SHAP_PATH.exists():
            shap_summary = json.loads(SHAP_PATH.read_text(encoding="utf-8"))
            st.markdown("**Top SHAP Features**")
            top_rows = shap_summary.get("top_features", [])[:15]
            if top_rows:
                shap_df = pd.DataFrame(top_rows)
                st.bar_chart(shap_df.set_index("feature"))
                st.dataframe(shap_df, use_container_width=True)
            else:
                st.info("SHAP file exists but no top_features found.")
        else:
            st.info("No SHAP summary found yet.")


def section_case_intelligence(orchestrator: RiskOrchestrator) -> None:
    st.subheader("Case Intelligence Monitor")

    case_limit = st.slider("Recent cases to load", min_value=20, max_value=500, value=150, step=10)
    case_rows = orchestrator.list_cases(limit=case_limit)

    if not case_rows:
        st.info("No cases available yet. Run detections or batch simulation first.")
        return

    cases_df = pd.DataFrame(case_rows)
    risk_col, exposure_col, leaderboard_col = st.columns([1, 1, 1.2], gap="large")

    with risk_col:
        st.metric("Total Cases", int(len(cases_df)))
        st.metric("Avg Risk", f"{cases_df['risk_score'].mean():.2f}")
    with exposure_col:
        high_count = int((cases_df["exposure_level"] == "High").sum())
        medium_count = int((cases_df["exposure_level"] == "Medium").sum())
        st.metric("High Exposure", high_count)
        st.metric("Medium Exposure", medium_count)
    with leaderboard_col:
        st.markdown("**Highest Risk Accounts**")
        top_df = cases_df.sort_values("risk_score", ascending=False).head(10)
        st.dataframe(top_df[["account_id", "case_id", "risk_score", "exposure_level"]], use_container_width=True)

    st.markdown("**Exposure Mix**")
    exposure_counts = cases_df["exposure_level"].value_counts().rename_axis("exposure").reset_index(name="count")
    st.bar_chart(exposure_counts.set_index("exposure"))

    st.markdown("**Recent Cases Table**")
    display_cols = ["case_id", "account_id", "risk_score", "exposure_level"]
    for optional_col in ("feedback", "notes"):
        if optional_col not in cases_df.columns:
            cases_df[optional_col] = "-"
    display_cols += ["feedback", "notes"]
    st.dataframe(
        cases_df[display_cols].fillna("-"),
        use_container_width=True,
    )


# ── Data Query Assistant ─────────────────────────────────────────────────────


def _get_ml_artifacts_summary() -> str:
    """Build a compact summary of current ML artifacts for LLM context."""
    parts: list[str] = []
    if METADATA_PATH.exists():
        try:
            meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
            parts.append(
                f"Model: rows={meta.get('rows_used')}, "
                f"ROC-AUC={meta.get('roc_auc')}, "
                f"threshold={meta.get('threshold')}, "
                f"features={meta.get('feature_count', 'n/a')}"
            )
        except (json.JSONDecodeError, OSError):
            pass
    if SHAP_PATH.exists():
        try:
            shap_data = json.loads(SHAP_PATH.read_text(encoding="utf-8"))
            top = shap_data.get("top_features", [])[:5]
            if top:
                feat_str = ", ".join(f"{f['feature']}={f.get('importance', 'n/a')}" for f in top)
                parts.append(f"Top SHAP features: {feat_str}")
        except (json.JSONDecodeError, OSError):
            pass
    return "\n".join(parts) if parts else "No ML artifacts available."


def _get_ml_metadata_dict() -> dict:
    """Return ML model metadata as a dict (empty if unavailable)."""
    if METADATA_PATH.exists():
        try:
            return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _get_shap_top_features(n: int = 5) -> list[dict]:
    """Return top-N SHAP features as list of dicts."""
    if SHAP_PATH.exists():
        try:
            data = json.loads(SHAP_PATH.read_text(encoding="utf-8"))
            return data.get("top_features", [])[:n]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _build_risk_meter_svg(score: float, max_score: float = 100.0) -> str:
    """Return SVG markup for a circular risk meter gauge."""
    pct = min(max(score / max_score, 0.0), 1.0)
    radius = 44
    circumference = 2 * 3.14159 * radius
    offset = circumference * (1 - pct)
    if pct >= 0.7:
        color = "#ef4444"
        label = "HIGH"
    elif pct >= 0.4:
        color = "#f59e0b"
        label = "MEDIUM"
    else:
        color = "#22c55e"
        label = "LOW"
    return (
        f'<div class="dqa-risk-meter">'
        f'<div class="dqa-meter-ring">'
        f'<svg width="110" height="110">'
        f'<circle cx="55" cy="55" r="{radius}" stroke="rgba(120,120,120,0.15)" '
        f'stroke-width="8" fill="none"/>'
        f'<circle cx="55" cy="55" r="{radius}" stroke="{color}" '
        f'stroke-width="8" fill="none" stroke-linecap="round" '
        f'stroke-dasharray="{circumference}" stroke-dashoffset="{offset:.1f}"/>'
        f'</svg>'
        f'<div class="dqa-meter-value" style="color:{color};">{score:.0f}</div>'
        f'</div>'
        f'<div class="dqa-meter-label">{label} RISK</div>'
        f'<div class="dqa-meter-sublabel">Composite Score (0–{max_score:.0f})</div>'
        f'</div>'
    )


def _build_entity_html(name: str, entity_type: str, score: float, meta_text: str = "") -> str:
    """Return HTML for one entity item in the related-entities panel."""
    avatar_bg = "#1e3a5f" if entity_type == "account" else (
        "#3b1f5f" if entity_type == "bank" else "#1f3f2f"
    )
    initials = name[:2].upper() if name else "??"
    score_cls = "high" if score >= 70 else ("medium" if score >= 40 else "low")
    return (
        f'<div class="dqa-entity-item">'
        f'<div class="dqa-entity-avatar" style="background:{avatar_bg}; color:#e2e8f0;">'
        f'{initials}</div>'
        f'<div class="dqa-entity-info">'
        f'<div class="dqa-entity-name">{name}</div>'
        f'<div class="dqa-entity-meta">{meta_text}</div>'
        f'</div>'
        f'<div class="dqa-entity-score {score_cls}">{score:.0f}</div>'
        f'</div>'
    )


def _build_action_html(icon: str, text: str, badge: str = "", badge_cls: str = "normal") -> str:
    """Return HTML for one suggested-action card."""
    badge_html = (
        f'<span class="dqa-action-badge {badge_cls}">{badge}</span>'
        if badge else ""
    )
    return (
        f'<div class="dqa-action-item">'
        f'<span class="dqa-action-icon">{icon}</span>'
        f'<span class="dqa-action-text">{text}</span>'
        f'{badge_html}'
        f'</div>'
    )


def _derive_context_insights(
    rule_store: SessionRuleStore,
) -> dict:
    """Derive dynamic context insights from session state and the latest LLM response.

    Returns dict with keys: risk_score, risk_entities, suggested_actions, model_status.
    """
    insights: dict = {
        "risk_score": 0.0,
        "risk_level": "N/A",
        "risk_entities": [],
        "suggested_actions": [],
        "model_status": "offline",
    }

    # ── Risk score from last live detection ────
    last_result = st.session_state.get("last_result")
    if last_result is not None:
        insights["risk_score"] = getattr(last_result, "risk_score", 0.0)
        score = insights["risk_score"]
        insights["risk_level"] = "High" if score >= 70 else ("Medium" if score >= 40 else "Low")

        # Extract entities from result
        acct = getattr(last_result, "account_id", None) or st.session_state.get("_dqa_last_account", "")
        if acct:
            insights["risk_entities"].append({
                "name": acct,
                "type": "account",
                "score": score,
                "meta": f"Exposure: {getattr(last_result, 'exposure_level', 'unknown')}",
            })

        # Derive actions from risk level
        if score >= 70:
            insights["suggested_actions"] = [
                {"icon": "🚨", "text": "Generate SAR Report", "badge": "Urgent", "badge_cls": "priority"},
                {"icon": "🔒", "text": "Freeze Account", "badge": "High", "badge_cls": "priority"},
                {"icon": "🔍", "text": "Deep Graph Analysis", "badge": "Rec", "badge_cls": "normal"},
                {"icon": "📊", "text": "Export Evidence Package", "badge": "", "badge_cls": "info"},
            ]
        elif score >= 40:
            insights["suggested_actions"] = [
                {"icon": "📋", "text": "Review Transaction History", "badge": "Rec", "badge_cls": "normal"},
                {"icon": "🔍", "text": "Expand Entity Network", "badge": "", "badge_cls": "info"},
                {"icon": "⚠️", "text": "Flag for Enhanced Due Diligence", "badge": "EDD", "badge_cls": "normal"},
            ]
        else:
            insights["suggested_actions"] = [
                {"icon": "✅", "text": "Mark as Reviewed", "badge": "", "badge_cls": "info"},
                {"icon": "📊", "text": "Run Batch Analysis", "badge": "", "badge_cls": "info"},
            ]
    else:
        # No detection yet — default actions
        insights["suggested_actions"] = [
            {"icon": "⚡", "text": "Run Live Detection First", "badge": "Start", "badge_cls": "normal"},
            {"icon": "📂", "text": "Upload Dataset for Analysis", "badge": "", "badge_cls": "info"},
            {"icon": "🧪", "text": "Train Model in Studio", "badge": "", "badge_cls": "info"},
        ]

    # ── Enrich entities from chat context ─────
    last_entities = st.session_state.get("_dqa_context_entities", [])
    for ent in last_entities:
        if ent not in insights["risk_entities"]:
            insights["risk_entities"].append(ent)

    # ── Model status ──────────────────────────
    meta = _get_ml_metadata_dict()
    insights["model_status"] = "online" if meta else "offline"
    insights["model_meta"] = meta

    return insights


def _render_context_sidebar(rule_store: SessionRuleStore) -> None:
    """Render the right-hand context insights sidebar within the DQA tab."""
    insights = _derive_context_insights(rule_store)

    # ── 1. Risk Score Meter ──────────────────
    st.markdown(
        '<div class="dqa-insight-panel">'
        '<h5>📊 Risk Assessment</h5>',
        unsafe_allow_html=True,
    )
    st.markdown(
        _build_risk_meter_svg(insights["risk_score"]),
        unsafe_allow_html=True,
    )
    # Layer breakdown if we have a live result
    last_result = st.session_state.get("last_result")
    if last_result is not None and hasattr(last_result, "risk_breakdown"):
        bd = last_result.risk_breakdown
        raw_s = bd["raw"].score if "raw" in bd else 0
        ml_s = bd["ml"].score if "ml" in bd else 0
        gr_s = bd["graph"].score if "graph" in bd else 0
        st.markdown(
            f'<div style="display:flex; justify-content:space-around; font-size:0.75rem; color:#94a3b8; margin-top:0.4rem;">'
            f'<span>RAW <strong>{raw_s:.1f}</strong></span>'
            f'<span>ML <strong>{ml_s:.1f}</strong></span>'
            f'<span>GRAPH <strong>{gr_s:.1f}</strong></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 2. Related Entities ──────────────────
    entities = insights["risk_entities"]
    st.markdown(
        '<div class="dqa-insight-panel">'
        f'<h5>🔗 Related Entities ({len(entities)})</h5>',
        unsafe_allow_html=True,
    )
    if entities:
        for ent in entities[:6]:
            st.markdown(
                _build_entity_html(
                    name=ent["name"],
                    entity_type=ent.get("type", "account"),
                    score=ent.get("score", 0),
                    meta_text=ent.get("meta", ""),
                ),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="font-size:0.82rem; color:#64748b; padding:0.5rem 0;">'
            'No entities detected yet. Run a risk analysis or ask about a specific account.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 3. Suggested Actions ─────────────────
    actions = insights["suggested_actions"]
    st.markdown(
        '<div class="dqa-insight-panel">'
        '<h5>⚡ Suggested Actions</h5>',
        unsafe_allow_html=True,
    )
    for act in actions:
        st.markdown(
            _build_action_html(
                icon=act["icon"],
                text=act["text"],
                badge=act.get("badge", ""),
                badge_cls=act.get("badge_cls", "normal"),
            ),
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 4. Active Rules Summary ──────────────
    active_rules = rule_store.get_rules()
    st.markdown(
        '<div class="dqa-insight-panel">'
        f'<h5>📋 Active Rules ({len(active_rules)})</h5>',
        unsafe_allow_html=True,
    )
    if active_rules:
        for r in active_rules[:5]:
            st.markdown(
                f'<div style="font-size:0.78rem; padding:2px 0; color:#cbd5e1;">'
                f'• <strong>[{r.rule_type}]</strong> {r.description[:55]}</div>',
                unsafe_allow_html=True,
            )
        if len(active_rules) > 5:
            st.caption(f"…and {len(active_rules) - 5} more")
    else:
        st.markdown(
            '<div style="font-size:0.78rem; color:#64748b; padding:0.3rem 0;">'
            'No rules active. Go to Datasets → Compliance Rules to configure.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 5. Model Info Compact ────────────────
    meta = insights.get("model_meta", {})
    status = insights["model_status"]
    dot_cls = "online" if status == "online" else "offline"
    st.markdown(
        '<div class="dqa-insight-panel">'
        f'<h5><span class="dqa-status-dot {dot_cls}"></span> Model Status</h5>',
        unsafe_allow_html=True,
    )
    if meta:
        st.markdown(
            f'<div style="font-size:0.8rem; color:#94a3b8;">'
            f'ROC-AUC: <strong>{meta.get("roc_auc", "n/a")}</strong> · '
            f'Threshold: {meta.get("threshold", "n/a")} · '
            f'Features: {meta.get("feature_count", "n/a")}'
            f'</div>',
            unsafe_allow_html=True,
        )
        top_feats = _get_shap_top_features(3)
        if top_feats:
            feat_html = " · ".join(
                f'<code style="font-size:0.72rem;">{f["feature"]}</code>'
                for f in top_feats
            )
            st.markdown(
                f'<div style="font-size:0.75rem; color:#64748b; margin-top:0.3rem;">'
                f'Top features: {feat_html}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="font-size:0.8rem; color:#64748b;">No trained model detected. '
            'Train one in Model Studio.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def section_ai_chat(rule_store: SessionRuleStore) -> None:
    """Data Query Assistant — conversational AI + live context insights for AML analysis."""

    # ── Header bar ───────────────────────────────
    import os as _os

    llm_disabled = _os.getenv("AEGIS_LLM_ENABLED", "").lower() in {"0", "false", "no", "off"}
    # Auto-detect: try a quick Ollama ping to determine status
    _ollama_ok = False
    if not llm_disabled:
        try:
            from urllib import request as _req
            _ping = _req.urlopen("http://localhost:11434/api/tags", timeout=2)
            _ping.close()
            _ollama_ok = True
        except Exception:
            pass
    dot_cls = "online" if _ollama_ok else "offline"
    dot_label = "LLM Online" if _ollama_ok else "LLM Offline"

    st.markdown(
        f'<div class="dqa-header">'
        f'<div class="dqa-header-left">'
        f'<h3 style="margin:0;">🔍 Data Query Assistant</h3>'
        f'</div>'
        f'<div class="dqa-header-right">'
        f'<span class="dqa-status-dot {dot_cls}"></span>'
        f'<span style="font-size:0.78rem; color:#94a3b8;">{dot_label}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Ask natural language questions about transactions, entities, risk patterns, "
        "or compliance concerns. Contextual insights update dynamically based on your queries."
    )

    # ── Two-column layout: Chat (left) + Insights (right) ──
    chat_col, insight_col = st.columns([2.2, 1], gap="medium")

    # ── RIGHT column: Context Insights Sidebar ───
    with insight_col:
        _render_context_sidebar(rule_store)

    # ── LEFT column: Chat Panel ──────────────────
    with chat_col:

        def _as_reasoning_markdown(text: str) -> str:
            body = (text or "").strip().replace("\n", "\n> ")
            return f"> 🧠 **Reasoning**\n>\n> {body}"

        def _type_markdown(text: str, *, chunk_size: int = 16, delay_s: float = 0.01) -> None:
            import time as _time

            content = (text or "").strip()
            if not content:
                return
            if len(content) > 2800:
                st.markdown(content)
                return
            placeholder = st.empty()
            for idx in range(chunk_size, len(content) + chunk_size, chunk_size):
                placeholder.markdown(content[:idx])
                _time.sleep(delay_s)
            placeholder.markdown(content)

        # ── Toolbar (export / history) ───────────
        tb1, tb2, tb3, _tbfill = st.columns([1, 1, 1, 3])
        with tb1:
            if st.button("🕐 History", key="dqa_history_toggle", use_container_width=True):
                st.session_state["_dqa_show_history"] = not st.session_state.get("_dqa_show_history", False)
                st.rerun()
        with tb2:
            export_ready = bool(st.session_state.get("chat_history"))
            if st.button("📥 Export", key="dqa_export", disabled=not export_ready, use_container_width=True):
                # Build export text
                lines: list[str] = ["AEGIS-AML Data Query Assistant — Chat Export", "=" * 50, ""]
                for msg in st.session_state.get("chat_history", []):
                    role = msg["role"].upper()
                    if "sections" in msg:
                        content = msg["sections"].get("result", "(no result)")
                    else:
                        content = msg.get("content", "")
                    lines.append(f"[{role}]\n{content}\n")
                export_text = "\n".join(lines)
                st.download_button(
                    label="Download .txt",
                    data=export_text,
                    file_name="aegis_chat_export.txt",
                    mime="text/plain",
                    key="dqa_download_txt",
                )
        with tb3:
            if st.button("🗑️ Clear", key="dqa_clear_chat", use_container_width=True):
                st.session_state["chat_history"] = []
                st.session_state.pop("_dqa_context_entities", None)
                st.rerun()

        # ── History panel (collapsible) ──────────
        if st.session_state.get("_dqa_show_history") and st.session_state.get("chat_history"):
            with st.expander("🕐 Recent Queries", expanded=True):
                for i, msg in enumerate(st.session_state["chat_history"]):
                    if msg["role"] == "user":
                        q_text = msg.get("content", "")[:80]
                        st.markdown(
                            f'<div style="font-size:0.8rem; padding:2px 0; color:#cbd5e1;">'
                            f'{i // 2 + 1}. {q_text}</div>',
                            unsafe_allow_html=True,
                        )

        # ── Initialize chat state ────────────────
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []

        # ── Greeting + suggested prompts (empty state) ─
        if not st.session_state["chat_history"]:
            st.markdown(
                '<div class="dqa-greeting">'
                '<h4>👋 How can I help with your investigation?</h4>'
                '<p>I can analyze transactions, explain risk scores, explore entity networks, '
                'and help with AML compliance questions.</p>'
                '</div>',
                unsafe_allow_html=True,
            )

            _suggested = [
                ("🔍", "Analyze risk scoring", "How does the 3-layer risk scoring work? Explain RAW, ML, and Graph layers."),
                ("📊", "Top SHAP features", "What are the top SHAP features driving the ML model's fraud predictions?"),
                ("🌐", "Cross-border patterns", "What cross-border transaction patterns are most indicative of money laundering?"),
                ("⚡", "Velocity risk signals", "How does transaction velocity (tx_count_last_hour) affect the risk score?"),
                ("🏦", "Investigation workflow", "What are the recommended investigation steps for a high-risk flagged account?"),
                ("📋", "Active rules impact", "How do the currently active session rules affect risk scoring?"),
                ("🔗", "Graph intelligence", "How does the graph layer detect mule chains and suspicious clusters?"),
                ("🛡️", "SAR report guidance", "What information is required for a Suspicious Activity Report (SAR)?"),
            ]
            prompt_cols = st.columns(2)
            for idx, (icon, label, prompt_text) in enumerate(_suggested):
                col = prompt_cols[idx % 2]
                with col:
                    if st.button(
                        f"{icon}  {label}",
                        key=f"dqa_suggest_{idx}",
                        use_container_width=True,
                    ):
                        st.session_state["_pending_prompt"] = prompt_text
                        st.rerun()

        # ── Display chat history ─────────────────
        for msg in st.session_state["chat_history"]:
            role = msg["role"]
            with st.chat_message(role):
                if role == "assistant" and "sections" in msg:
                    sections = msg["sections"]
                    # Show full reasoning
                    if sections.get("plan"):
                        st.markdown(_as_reasoning_markdown(sections["plan"]))
                    # Main result
                    if sections.get("result"):
                        st.markdown(sections["result"])
                    # Follow-up chips
                    if sections.get("suggested_next"):
                        st.markdown(
                            '<div style="margin-top:0.5rem; font-size:0.78rem; color:#64748b;">'
                            '💡 <strong>Follow-up:</strong></div>',
                            unsafe_allow_html=True,
                        )
                        # Parse suggested_next into individual items
                        follow_items = [
                            line.strip().lstrip("- •*·")
                            for line in sections["suggested_next"].split("\n")
                            if line.strip() and line.strip() not in ("-", "•")
                        ]
                        for fi_idx, fi_text in enumerate(follow_items[:4]):
                            if st.button(
                                f"↪ {fi_text[:60]}",
                                key=f"dqa_follow_{msg.get('_ts', id(msg))}_{fi_idx}",
                            ):
                                st.session_state["_pending_prompt"] = fi_text
                                st.rerun()
                    # Rule injection notice
                    if msg.get("rules_injected"):
                        st.success(
                            f"✅ {len(msg['rules_injected'])} rule(s) injected into session."
                        )
                        for r in msg["rules_injected"]:
                            st.markdown(f"- **[{r['rule_type']}]** {r['description']}")
                else:
                    st.markdown(msg.get("content", ""))

        # ── Chat input ───────────────────────────
        pending = st.session_state.pop("_pending_prompt", None)
        user_input = pending or st.chat_input(
            "Ask about transactions, entities, risk patterns, compliance…"
        )

        if user_input:
            # Append user message
            st.session_state["chat_history"].append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Handle special commands
            lower_input = user_input.strip().lower()
            if lower_input in ("show rules", "list rules"):
                active = rule_store.get_rules()
                if active:
                    content = "**Active session rules:**\n" + "\n".join(
                        f"{i+1}. **[{r.rule_type}]** {r.description}" for i, r in enumerate(active)
                    )
                else:
                    content = "No session rules are currently active."
                assistant_msg: dict = {"role": "assistant", "content": content}
                st.session_state["chat_history"].append(assistant_msg)
                with st.chat_message("assistant"):
                    st.markdown(content)
                st.rerun()
                return

            if lower_input in ("clear rules", "reset rules"):
                rule_store.clear()
                set_session_rules([])
                content = "✅ All session rules have been cleared."
                assistant_msg = {"role": "assistant", "content": content}
                st.session_state["chat_history"].append(assistant_msg)
                with st.chat_message("assistant"):
                    st.markdown(content)
                st.rerun()
                return

            if lower_input in ("export", "export chat"):
                content = "Use the **📥 Export** button in the toolbar above to download this conversation."
                assistant_msg = {"role": "assistant", "content": content}
                st.session_state["chat_history"].append(assistant_msg)
                with st.chat_message("assistant"):
                    st.markdown(content)
                st.rerun()
                return

            # ── Check for rule injection ─────────
            rules_injected_dicts: list[dict] = []
            if detect_rules(user_input):
                new_rules = parse_rules(user_input)
                if new_rules:
                    all_rules = rule_store.add_rules(new_rules)
                    set_session_rules(all_rules)
                    rules_injected_dicts = [r.to_dict() for r in new_rules]

            # ── Extract entities from query for context sidebar ──
            _extract_entities_from_query(user_input)

            # ── Call LLM with session rules ──────
            active_rules = rule_store.get_rules()
            set_session_rules(active_rules)

            system_ctx = (
                "You are the AEGIS-AML Data Query Assistant. You help analysts explore "
                "anti-money-laundering datasets, explain risk scores, discuss SHAP features, "
                "analyse entity networks, and recommend investigation actions. "
                "You MUST honour all active session rules in your reasoning. "
                "When the user asks about a specific entity or account, include structured "
                "details like risk indicators, related accounts, and behavioral patterns."
            )
            ml_artifacts = _get_ml_artifacts_summary()

            with st.chat_message("assistant"):
                with st.spinner("Analyzing…"):
                    raw_response = chat_with_rules(
                        user_message=user_input,
                        session_rules=active_rules,
                        system_context=system_ctx,
                        ml_artifacts=ml_artifacts,
                    )

                import time as _time
                sections = format_llm_response(raw_response)

                # Show full reasoning with typing animation
                if sections.get("plan"):
                    _type_markdown(_as_reasoning_markdown(sections["plan"]), chunk_size=12, delay_s=0.008)

                # Main result
                if sections.get("result"):
                    _type_markdown(sections["result"], chunk_size=16, delay_s=0.008)

                # Suggested follow-ups as clickable chips
                if sections.get("suggested_next"):
                    st.markdown(
                        '<div style="margin-top:0.5rem; font-size:0.78rem; color:#64748b;">'
                        '💡 <strong>Follow-up:</strong></div>',
                        unsafe_allow_html=True,
                    )
                    follow_items = [
                        line.strip().lstrip("- •*·")
                        for line in sections["suggested_next"].split("\n")
                        if line.strip() and line.strip() not in ("-", "•")
                    ]
                    for fi_idx, fi_text in enumerate(follow_items[:4]):
                        if st.button(
                            f"↪ {fi_text[:60]}",
                            key=f"dqa_new_follow_{_time.time()}_{fi_idx}",
                        ):
                            st.session_state["_pending_prompt"] = fi_text
                            st.rerun()

                # Rule injection confirmation
                if rules_injected_dicts:
                    st.success(f"✅ {len(rules_injected_dicts)} rule(s) injected into session.")
                    for r in rules_injected_dicts:
                        st.markdown(f"- **[{r['rule_type']}]** {r['description']}")

            # Store in history
            assistant_msg = {
                "role": "assistant",
                "sections": sections,
                "_ts": _time.time(),
            }
            if rules_injected_dicts:
                assistant_msg["rules_injected"] = rules_injected_dicts
            st.session_state["chat_history"].append(assistant_msg)


def _extract_entities_from_query(user_input: str) -> None:
    """Heuristically extract account/entity mentions from user query and store in session state."""
    import re as _re

    entities: list[dict] = st.session_state.get("_dqa_context_entities", [])
    existing_names = {e["name"] for e in entities}

    # Match patterns like acct_1001, ACCT-2003, account X, etc.
    acct_patterns = _re.findall(r'\bacct[_-]?\d+\b', user_input, _re.IGNORECASE)
    for acct in acct_patterns:
        acct_upper = acct.upper()
        if acct_upper not in existing_names:
            entities.append({
                "name": acct_upper,
                "type": "account",
                "score": 50,  # neutral until scored
                "meta": "Mentioned in query",
            })
            existing_names.add(acct_upper)

    # Match patterns like "account 12345" or "account X"
    acct_mentions = _re.findall(r'\baccount\s+([A-Za-z0-9_-]+)', user_input, _re.IGNORECASE)
    for mention in acct_mentions:
        name = f"ACCT_{mention}" if not mention.upper().startswith("ACCT") else mention.upper()
        if name not in existing_names:
            entities.append({
                "name": name,
                "type": "account",
                "score": 50,
                "meta": "Mentioned in query",
            })
            existing_names.add(name)

    # Keep only last 10 entities
    st.session_state["_dqa_context_entities"] = entities[-10:]


# ── Data Generator Tab ───────────────────────────────────────────────────────


def section_data_generator() -> None:
    """Synthetic training data generator with preview, download, and save-to-train."""
    from app.services.data_generator import (
        SUPPORTED_SCHEMAS,
        GeneratorConfig,
        generate_data,
        generate_to_csv_string,
        get_schema_preview,
    )
    st.subheader("Synthetic Training Data Generator")
    st.caption(
        "Generate realistic AML/fraud transaction datasets in multiple schemas. "
        "Data can be previewed, downloaded as CSV, or saved directly for model training."
    )

    # ── Configuration controls ────────────────────
    config_col, preview_col = st.columns([1, 1.4], gap="large")

    with config_col:
        st.markdown("#### Generation Settings")

        schema = st.selectbox(
            "Data Schema",
            options=SUPPORTED_SCHEMAS,
            index=SUPPORTED_SCHEMAS.index("aml_cft"),
            format_func=lambda s: {"unified": "Unified (Model-Ready)", "paysim": "PaySim (Kaggle)", "aml_cft": "AML-CFT (Standard Upload)"}[s],
            help="AML-CFT is the standard upload format: Time, Date, Sender_account, Receiver_account, Amount, etc.",
        )

        num_rows = st.slider("Number of Rows", min_value=50, max_value=100_000, value=1000, step=50)
        fraud_ratio = st.slider("Fraud Ratio", min_value=0.01, max_value=0.80, value=0.15, step=0.01)
        seed = st.number_input("Random Seed", min_value=0, max_value=999999, value=42, step=1)

        with st.expander("Advanced Settings", expanded=False):
            num_accounts = st.number_input("Distinct Accounts", min_value=10, max_value=100_000, value=200, step=10)
            start_date = st.text_input("Start Date (AML-CFT)", value="2025-01-01")
            days_span = st.slider("Date Range (days, AML-CFT)", min_value=1, max_value=365, value=90)

        # Show schema columns
        columns = get_schema_preview(schema)
        st.markdown(f"**Schema columns:** `{'`, `'.join(columns)}`")

        # ── Action buttons ──────────────────────────
        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            generate_preview = st.button("Preview", use_container_width=True, type="primary")
        with btn_col2:
            generate_download = st.button("Download CSV", use_container_width=True)
        with btn_col3:
            save_for_training = st.button("Save & Train", use_container_width=True, type="secondary")

    # Build config object
    config = GeneratorConfig(
        num_rows=int(num_rows),
        fraud_ratio=float(fraud_ratio),
        schema=schema,
        seed=int(seed),
        num_accounts=int(num_accounts),
        start_date=start_date,
        days_span=int(days_span),
    )

    with preview_col:
        # ── Preview ──────────────────────────────────
        if generate_preview:
            with st.spinner(f"Generating {num_rows:,} rows ({schema})..."):
                df = generate_data(config)
                st.session_state["gen_preview_df"] = df

        preview_df = st.session_state.get("gen_preview_df")
        if preview_df is not None:
            df = preview_df
            fraud_col = "label" if "label" in df.columns else (
                "isFraud" if "isFraud" in df.columns else "Is_laundering"
            )
            fraud_count = int(df[fraud_col].sum())
            legit_count = len(df) - fraud_count

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Rows", f"{len(df):,}")
            m2.metric("Fraud", f"{fraud_count:,}")
            m3.metric("Legit", f"{legit_count:,}")
            m4.metric("Fraud %", f"{fraud_count / len(df) * 100:.1f}%")

            st.markdown("**Data Preview (first 50 rows)**")
            st.dataframe(df.head(50), use_container_width=True, height=350)

            # Distribution chart
            if "transaction_amount" in df.columns:
                st.markdown("**Amount Distribution by Label**")
                chart_df = df[[fraud_col, "transaction_amount"]].copy()
                chart_df[fraud_col] = chart_df[fraud_col].map({0: "Legit", 1: "Fraud"})
                chart_df = chart_df.rename(columns={fraud_col: "class"})
                st.bar_chart(
                    chart_df.groupby("class")["transaction_amount"].mean(),
                )
            elif "Amount" in df.columns:
                st.markdown("**Amount Distribution by Label**")
                chart_df = df[[fraud_col, "Amount"]].copy()
                chart_df[fraud_col] = chart_df[fraud_col].map({0: "Legit", 1: "Fraud"})
                chart_df = chart_df.rename(columns={fraud_col: "class"})
                st.bar_chart(
                    chart_df.groupby("class")["Amount"].mean(),
                )
        else:
            st.info("Click **Preview** to generate and inspect synthetic data before saving.")

    # ── Download handler ─────────────────────────
    if generate_download:
        with st.spinner("Generating CSV for download..."):
            csv_string = generate_to_csv_string(config)
            st.download_button(
                label="📥 Download CSV File",
                data=csv_string,
                file_name=f"aegis_synthetic_{schema}_{num_rows}rows.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── Save & Train handler ─────────────────────
    if save_for_training:
        with st.spinner(f"Generating {num_rows:,} rows and saving to data/training_transactions.csv..."):
            df = generate_data(config)
            output_path = DATA_PATH
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            st.session_state["gen_preview_df"] = df

        fraud_col = "label" if "label" in df.columns else (
            "isFraud" if "isFraud" in df.columns else "Is_laundering"
        )
        fraud_count = int(df[fraud_col].sum())

        st.success(
            f"✅ Saved {len(df):,} rows ({fraud_count:,} fraud, {len(df) - fraud_count:,} legit) "
            f"to `data/training_transactions.csv`\n\n"
            f"Go to the **Training Control** tab to train the model on this data."
        )


# ── Datasets Overview ─────────────────────────────────────────────────────────


def section_datasets_overview() -> None:
    """Datasets Overview — card grid with upload support and step-by-step analysis flow."""
    from app.services.dataset_manager import (
        list_datasets,
        upload_and_register,
        update_status,
        delete_dataset,
        scan_existing_data_dir,
        validate_upload_schema,
        UPLOAD_SCHEMA_COLUMNS,
        DatasetRecord,
        get_dataset,
    )

    # ── Route to the active step ──────────────────
    ds_step = st.session_state.get("ds_flow_step", "overview")
    ds_id = st.session_state.get("ds_analysis_id")

    if ds_step == "validate" and ds_id:
        ds = get_dataset(ds_id)
        if ds:
            _render_step_validation(ds, update_status, delete_dataset)
            return
        st.session_state["ds_flow_step"] = "overview"

    if ds_step == "rules" and ds_id:
        ds = get_dataset(ds_id)
        if ds:
            _render_step_rules(ds, update_status)
            return
        st.session_state["ds_flow_step"] = "overview"

    if ds_step == "analysis" and ds_id:
        ds = get_dataset(ds_id)
        if ds:
            _render_step_analysis(ds)
            return
        st.session_state["ds_flow_step"] = "overview"

    # ── Overview (cards grid) ─────────────────────
    st.subheader("Datasets Overview")
    st.caption(
        "Manage transaction datasets and risk analysis reports. "
        "Upload new files, inspect risk summaries, and open analysis in one click."
    )

    # Auto-discover
    if "datasets_scanned" not in st.session_state:
        count = scan_existing_data_dir()
        st.session_state["datasets_scanned"] = True
        if count:
            st.toast(f"Auto-registered {count} existing dataset(s) from data/")

    # ── Upload panel ──────────────────────────────
    if st.session_state.get("ds_upload_open", False):
        with st.container():
            st.markdown(
                '<div style="border:1px solid rgba(59,130,246,0.3); border-radius:12px; '
                'padding:1.2rem; background:rgba(59,130,246,0.04); margin-bottom:1rem;">',
                unsafe_allow_html=True,
            )
            up_hdr_l, up_hdr_r = st.columns([4, 1])
            with up_hdr_l:
                st.markdown("#### Upload New Dataset")
                st.caption(
                    "Accepted formats: **CSV**, **Excel** (.xlsx/.xls). "
                    "Expected AML-CFT schema with 12 columns."
                )
            with up_hdr_r:
                if st.button("✕ Close", key="close_upload"):
                    st.session_state["ds_upload_open"] = False
                    st.rerun()

            with st.expander("📋 View expected schema columns", expanded=False):
                cols_md = " | ".join(f"`{c}`" for c in UPLOAD_SCHEMA_COLUMNS)
                st.markdown(cols_md)

            upload_col, opts_col = st.columns([1.5, 1], gap="large")
            with upload_col:
                uploaded_file = st.file_uploader(
                    "Drop a CSV or Excel file",
                    type=["csv", "xlsx", "xls"],
                    key="ds_upload",
                )
            with opts_col:
                ds_name = st.text_input("Dataset Name (optional)", key="ds_name_input")
                ds_notes = st.text_input("Notes (optional)", key="ds_notes_input")
                ds_tags_raw = st.text_input(
                    "Tags (comma-separated)", key="ds_tags_input",
                    placeholder="e.g. aml-cft, synthetic, india-vda",
                )

            if uploaded_file is not None:
                try:
                    if uploaded_file.name.lower().endswith((".xls", ".xlsx")):
                        preview_cols = list(pd.read_excel(uploaded_file, nrows=0).columns)
                    else:
                        preview_cols = list(pd.read_csv(uploaded_file, nrows=0).columns)
                    uploaded_file.seek(0)
                    missing = validate_upload_schema(preview_cols)
                    if missing:
                        st.warning(
                            f"⚠️ Schema mismatch — missing columns: **{', '.join(missing)}**. "
                            f"The file may still be registered but analysis results could be limited."
                        )
                    else:
                        st.success("✅ Schema validated — all 12 AML-CFT columns present.")
                except Exception:
                    pass

                if st.button("📤 Upload & Register", type="primary", use_container_width=True):
                    tags = [t.strip() for t in ds_tags_raw.split(",") if t.strip()] if ds_tags_raw else []
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        record = upload_and_register(
                            uploaded_bytes=uploaded_file.getvalue(),
                            original_filename=uploaded_file.name,
                            name=ds_name.strip() or None,
                            notes=ds_notes.strip(),
                            tags=tags,
                        )
                    st.success(
                        f"✅ Registered **{record.name}** — "
                        f"{record.total_rows:,} rows, risk level: {record.risk_level}"
                    )
                    st.session_state["ds_upload_open"] = False
                    # Auto-navigate to validation step
                    st.session_state["ds_analysis_id"] = record.dataset_id
                    st.session_state["ds_flow_step"] = "validate"
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # ── Load datasets ─────────────────────────────
    datasets = list_datasets()

    if datasets:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Datasets", len(datasets))
        m2.metric("Total Transactions", f"{sum(d.total_rows for d in datasets):,}")
        high_count = sum(1 for d in datasets if d.risk_level == "High")
        m3.metric("High Risk", high_count)
        completed = sum(1 for d in datasets if d.status == "Completed")
        m4.metric("Analysed", f"{completed}/{len(datasets)}")

    if not datasets:
        only_col = st.columns(1)[0]
        with only_col:
            st.markdown(
                '<div class="ds-add-card">'
                '<div class="ds-add-icon">➕</div>'
                '<h4 style="margin:0;">Add New Dataset</h4>'
                '<p style="color:#64748b; margin:0.3rem 0 0.8rem 0;">Upload CSV or Excel file</p>'
                '<p style="color:#94a3b8; margin:0; font-size:0.8rem;">No datasets registered yet.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Add New Dataset", type="primary", use_container_width=True, key="btn_add_ds_empty"):
                st.session_state["ds_upload_open"] = True
                st.rerun()
        return

    # ── Card grid (4 per row) with add-card first ─
    st.markdown("")
    grid_items = [None] + datasets
    COLS_PER_ROW = 4
    for row_start in range(0, len(grid_items), COLS_PER_ROW):
        cols = st.columns(COLS_PER_ROW, gap="medium")
        for col_idx, item in enumerate(grid_items[row_start : row_start + COLS_PER_ROW]):
            with cols[col_idx]:
                if item is None:
                    st.markdown(
                        '<div class="ds-add-card">'
                        '<div class="ds-add-icon">➕</div>'
                        '<h4 style="margin:0;">Add New Dataset</h4>'
                        '<p style="color:#64748b; margin:0.3rem 0 0.8rem 0;">Upload CSV or Excel file</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Add New Dataset",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_add_ds_grid_{row_start}_{col_idx}",
                    ):
                        st.session_state["ds_upload_open"] = True
                        st.rerun()
                else:
                    _render_dataset_card(item)


# ── Helper: Step bar ─────────────────────────────────────────────────────────


def _render_step_bar(current: str) -> None:
    """Render the 4-step navigation bar at the top of flow pages."""
    steps = [
        ("1. Upload", "overview"),
        ("2. Validation & Processing", "validate"),
        ("3. Compliance Rules", "rules"),
        ("4. Analysis", "analysis"),
    ]
    bar_html = '<div class="step-bar">'
    hit_current = False
    for label, key in steps:
        if key == current:
            cls = "active"
            hit_current = True
        elif not hit_current:
            cls = "done"
        else:
            cls = ""
        bar_html += f'<div class="step-item {cls}">{label}</div>'
    bar_html += '</div>'
    st.markdown(bar_html, unsafe_allow_html=True)


# ── Helper: Badges ───────────────────────────────────────────────────────────


def _risk_badge_html(level: str) -> str:
    cls = {
        "High": "ds-badge-high",
        "Medium": "ds-badge-medium",
        "Low": "ds-badge-low",
    }.get(level, "ds-badge-unknown")
    return f'<span class="ds-badge {cls}">{level} Risk</span>'


def _status_badge_html(status: str) -> str:
    cls = {
        "Pending": "ds-badge-pending",
        "In Progress": "ds-badge-inprogress",
        "Completed": "ds-badge-completed",
    }.get(status, "ds-badge-unknown")
    return f'<span class="ds-badge {cls}">{status}</span>'


# ── Helper: Dataset card ─────────────────────────────────────────────────────


def _render_dataset_card(ds) -> None:
    """Render a single dataset card with click-to-analyze."""
    try:
        dt = ds.upload_date[:10]
    except Exception:
        dt = str(ds.upload_date)[:10]

    safe_name = str(ds.name).replace("<", "&lt;").replace(">", "&gt;")

    status_key = {
        "Completed": "completed",
        "In Progress": "inprogress",
        "Pending": "pending",
    }.get(ds.status, "pending")
    status_label = ds.status if ds.status in {"Completed", "In Progress", "Pending"} else "Pending"

    risk_pill = _risk_badge_html(ds.risk_level)
    topbar_cls = "completed" if status_key == "completed" else ("inprogress" if status_key == "inprogress" else "pending")

    st.markdown(
        f'<div class="ds-card">'
        f'<div class="ds-card-topbar {topbar_cls}"></div>'
        f'<div class="ds-header-row">'
        f'<span class="ds-status-pill {status_key}"><span class="ds-status-dot"></span>{status_label}</span>'
        f'</div>'
        f'<h4>{safe_name}</h4>'
        f'<div class="ds-meta">Uploaded: {dt} &middot; {ds.human_size}</div>'
        f'<div class="ds-stat" style="margin:0.45rem 0 0.2rem 0;">{ds.total_columns} columns &middot; Fraud {ds.fraud_pct}</div>'
        f'<div class="ds-tx-row"><span class="ds-label">Transactions</span><span class="ds-value">{ds.total_rows:,}</span></div>'
        f'<div class="ds-risk-row"><span class="ds-label">Risk Summary</span><span>{risk_pill}</span></div>'
        f'<div class="ds-stat" style="margin-top:0.45rem;">'
        f'Click below to continue workflow.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Completed datasets go straight to Analysis; others to Validate
    _btn_label = "📊 Open Analysis" if ds.status == "Completed" else "🔍 Analyse"
    _target_step = "analysis" if ds.status == "Completed" else "validate"
    if st.button(
        _btn_label,
        key=f"analyse_{ds.dataset_id}",
        use_container_width=True,
    ):
        st.session_state["ds_analysis_id"] = ds.dataset_id
        st.session_state["ds_flow_step"] = _target_step
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Dataset Validation & Processing
# ══════════════════════════════════════════════════════════════════════════════


def _render_step_validation(ds, update_status_fn, delete_fn) -> None:
    """Step 2: Validation summary, data quality checks, dataset info card."""
    from app.services.dataset_manager import validate_upload_schema, UPLOAD_SCHEMA_COLUMNS

    _render_step_bar("validate")

    # ── Load dataset ──────────────────────────────
    ds_path = Path(ds.file_path)
    df_full = None
    load_error = None
    if ds_path.exists():
        try:
            suffix = ds_path.suffix.lower()
            df_full = pd.read_excel(ds_path) if suffix in (".xls", ".xlsx") else pd.read_csv(ds_path)
        except Exception as exc:
            load_error = str(exc)

    # ── Run all validation checks ─────────────────
    checks: list[dict] = []

    # 1) Schema validation
    if df_full is not None:
        missing = validate_upload_schema(list(df_full.columns))
        if not missing:
            checks.append({
                "name": "Schema Validation",
                "status": "pass",
                "icon": "✅",
                "detail": "All 12 AML-CFT columns present.",
                "action": None,
            })
        else:
            checks.append({
                "name": "Schema Validation",
                "status": "fail",
                "icon": "❌",
                "detail": f"Missing columns: {', '.join(missing)}",
                "action": None,
            })
    else:
        checks.append({
            "name": "Schema Validation",
            "status": "fail",
            "icon": "❌",
            "detail": load_error or "File not found on disk.",
            "action": None,
        })

    if df_full is not None:
        # 2) Missing value check
        total_null = int(df_full.isnull().sum().sum())
        null_pct = df_full.isnull().mean().mean() * 100
        if null_pct < 1:
            checks.append({
                "name": "Missing Values",
                "status": "pass",
                "icon": "✅",
                "detail": f"{total_null:,} missing values ({null_pct:.2f}% overall). Data is clean.",
                "action": None,
            })
        elif null_pct < 5:
            checks.append({
                "name": "Missing Values",
                "status": "warn",
                "icon": "⚠️",
                "detail": f"{total_null:,} missing values ({null_pct:.1f}%). Some columns have gaps.",
                "action": None,
            })
        else:
            null_cols = [c for c in df_full.columns if df_full[c].isnull().mean() > 0.05]
            checks.append({
                "name": "Missing Values",
                "status": "fail",
                "icon": "❌",
                "detail": f"{total_null:,} missing values ({null_pct:.1f}%). Heavy nulls in: {', '.join(null_cols[:5])}",
                "action": None,
            })

        # 3) Duplicate detection
        dup_count = int(df_full.duplicated().sum())
        if dup_count == 0:
            checks.append({
                "name": "Duplicate Detection",
                "status": "pass",
                "icon": "✅",
                "detail": "No duplicate rows detected.",
                "action": None,
            })
        else:
            checks.append({
                "name": "Duplicate Detection",
                "status": "warn",
                "icon": "⚠️",
                "detail": f"{dup_count:,} duplicate rows found.",
                "action": "review_duplicates",
            })

        # 4) Data consistency
        consistency_issues: list[str] = []
        if "Amount" in df_full.columns:
            neg = int((df_full["Amount"] < 0).sum())
            if neg > 0:
                consistency_issues.append(f"{neg} negative amounts")
        if "Is_laundering" in df_full.columns:
            bad_labels = set(df_full["Is_laundering"].dropna().unique()) - {0, 1}
            if bad_labels:
                consistency_issues.append(f"Unexpected labels: {bad_labels}")
        if "Date" in df_full.columns:
            try:
                dates = pd.to_datetime(df_full["Date"], errors="coerce")
                bad_dates = int(dates.isna().sum() - df_full["Date"].isna().sum())
                if bad_dates > 0:
                    consistency_issues.append(f"{bad_dates} unparseable dates")
            except Exception:
                pass

        if not consistency_issues:
            checks.append({
                "name": "Data Consistency",
                "status": "pass",
                "icon": "✅",
                "detail": "All values within expected ranges. Dates and labels are valid.",
                "action": None,
            })
        else:
            checks.append({
                "name": "Data Consistency",
                "status": "warn" if len(consistency_issues) <= 1 else "fail",
                "icon": "⚠️" if len(consistency_issues) <= 1 else "❌",
                "detail": "; ".join(consistency_issues),
                "action": None,
            })

    # ── Compute overall readiness ─────────────────
    passed = sum(1 for c in checks if c["status"] == "pass")
    total_checks = len(checks)
    has_failures = any(c["status"] == "fail" for c in checks)
    progress = passed / total_checks if total_checks > 0 else 0

    if not has_failures and passed == total_checks:
        status_label = "Ready for Processing"
        status_color = "#22c55e"
    elif has_failures:
        status_label = "Issues Found"
        status_color = "#ef4444"
    else:
        status_label = "Review Recommended"
        status_color = "#f59e0b"

    # ── Layout: left = checks, right = summary card ─
    left_col, right_col = st.columns([3, 1.5], gap="large")

    with left_col:
        st.markdown(f"### 📋 Validation & Processing — {ds.name}")

        # Progress bar + status label
        st.progress(progress)
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:0.5rem; margin:-0.5rem 0 1rem 0;">'
            f'<span style="display:inline-block; width:10px; height:10px; border-radius:50%; '
            f'background:{status_color};"></span>'
            f'<span style="font-weight:600; color:{status_color};">{status_label}</span>'
            f'<span style="color:#64748b; font-size:0.85rem;">— {passed}/{total_checks} checks passed</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Check cards ──────────────────────────────
        for check in checks:
            cls = check["status"]
            st.markdown(
                f'<div class="vcheck-card {cls}">'
                f'<div class="vcheck-title">{check["icon"]} {check["name"]}</div>'
                f'<div class="vcheck-detail">{check["detail"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Action button for duplicates
            if check.get("action") == "review_duplicates" and df_full is not None:
                with st.expander("📝 Review Duplicates", expanded=False):
                    dups = df_full[df_full.duplicated(keep=False)].head(50)
                    st.dataframe(dups, use_container_width=True, height=200)
                    if st.button("🗑️ Remove Duplicates & Re-save", key="rm_dups"):
                        df_deduped = df_full.drop_duplicates()
                        if ds_path.suffix.lower() in (".xls", ".xlsx"):
                            df_deduped.to_excel(ds_path, index=False)
                        else:
                            df_deduped.to_csv(ds_path, index=False)
                        # Update the registry stats
                        from app.services.dataset_manager import _recompute_stats
                        _recompute_stats(ds.dataset_id, ds_path)
                        st.success(f"Removed {len(df_full) - len(df_deduped):,} duplicates. File re-saved.")
                        st.rerun()

        # ── Data preview (collapsible) ────────────────
        if df_full is not None:
            with st.expander("📊 Data Preview (first 30 rows)", expanded=False):
                st.dataframe(df_full.head(30), use_container_width=True, height=280)

    with right_col:
        # ── Dataset summary info card ─────────────────
        try:
            dt = ds.upload_date[:10]
        except Exception:
            dt = str(ds.upload_date)[:10]

        date_range = "—"
        if df_full is not None and "Date" in df_full.columns:
            try:
                dates = pd.to_datetime(df_full["Date"], errors="coerce").dropna()
                if len(dates) > 0:
                    date_range = f"{dates.min().strftime('%Y-%m-%d')} → {dates.max().strftime('%Y-%m-%d')}"
            except Exception:
                pass

        st.markdown(
            f'<div class="info-card">'
            f'<h5>📁 Dataset Summary</h5>'
            f'<div class="info-row"><span class="info-label">File Name</span>'
            f'<span class="info-value">{Path(ds.file_path).name}</span></div>'
            f'<div class="info-row"><span class="info-label">Upload Date</span>'
            f'<span class="info-value">{dt}</span></div>'
            f'<div class="info-row"><span class="info-label">Transactions</span>'
            f'<span class="info-value">{ds.total_rows:,}</span></div>'
            f'<div class="info-row"><span class="info-label">Columns</span>'
            f'<span class="info-value">{ds.total_columns}</span></div>'
            f'<div class="info-row"><span class="info-label">Date Range</span>'
            f'<span class="info-value">{date_range}</span></div>'
            f'<div class="info-row"><span class="info-label">File Size</span>'
            f'<span class="info-value">{ds.human_size}</span></div>'
            f'<div class="info-row"><span class="info-label">Risk Level</span>'
            f'<span class="info-value">{_risk_badge_html(ds.risk_level)}</span></div>'
            f'<div class="info-row"><span class="info-label">Status</span>'
            f'<span class="info-value">{_status_badge_html(ds.status)}</span></div>'
            f'<div class="info-row"><span class="info-label">Fraud %</span>'
            f'<span class="info-value">{ds.fraud_pct}</span></div>'
            f'<div class="info-row"><span class="info-label">SHA-256</span>'
            f'<span class="info-value" style="font-size:0.72rem;">{ds.sha256[:16]}…</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("")

        # ── Quick actions ─────────────────────────────
        if st.button("📥 Use for Training", key=f"train_{ds.dataset_id}", use_container_width=True):
            if ds_path.exists():
                import shutil
                dest = ds_path.resolve().parents[1] / "training_transactions.csv"
                if ds_path.suffix.lower() == ".csv":
                    shutil.copy2(ds_path, dest)
                else:
                    df_tmp = pd.read_excel(ds_path)
                    df_tmp.to_csv(dest, index=False)
                st.success("Copied to training_transactions.csv")

        if st.button("🗑️ Delete Dataset", key=f"del_{ds.dataset_id}", use_container_width=True):
            delete_fn(ds.dataset_id)
            st.session_state["ds_flow_step"] = "overview"
            st.session_state["ds_analysis_id"] = None
            st.rerun()

    # ── Bottom navigation ─────────────────────────
    st.markdown("---")
    nav_l, nav_spacer, nav_r = st.columns([1, 2, 1])
    with nav_l:
        if st.button("← Go Back", key="val_back", use_container_width=True):
            st.session_state["ds_flow_step"] = "overview"
            st.session_state["ds_analysis_id"] = None
            st.rerun()
    with nav_r:
        proceed_disabled = has_failures and (passed == 0)
        if st.button(
            "Proceed to Rules →",
            key="val_proceed",
            type="primary",
            use_container_width=True,
            disabled=proceed_disabled,
        ):
            update_status_fn(ds.dataset_id, "In Progress")
            st.session_state["ds_flow_step"] = "rules"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Compliance Rules
# ══════════════════════════════════════════════════════════════════════════════


# Default AML compliance rules
_DEFAULT_RULES: list[dict] = [
    {
        "id": "AML-R001",
        "name": "High-Value Transaction Alert",
        "description": "Flag any transaction with Amount > ₹50,000 for enhanced due diligence.",
        "severity": "High",
        "conditions": ["Amount > 50000"],
        "active": True,
    },
    {
        "id": "AML-R002",
        "name": "Cross-Border Transfer Check",
        "description": "Flag cross-border payments where sender and receiver are in different countries.",
        "severity": "High",
        "conditions": ["Sender_bank_location ≠ Receiver_bank_location"],
        "active": True,
    },
    {
        "id": "AML-R003",
        "name": "Currency Mismatch Detection",
        "description": "Flag when Payment_currency differs from Received_currency.",
        "severity": "Medium",
        "conditions": ["Payment_currency ≠ Received_currency"],
        "active": True,
    },
    {
        "id": "AML-R004",
        "name": "High-Risk Payment Type",
        "description": "Flag Cash deposits and Cross-border payments for additional scrutiny.",
        "severity": "Medium",
        "conditions": ["Payment_type IN (Cash deposit, Cross-border)"],
        "active": True,
    },
    {
        "id": "AML-R005",
        "name": "Known Laundering Pattern",
        "description": "Flag transactions with a non-empty Laundering_type field.",
        "severity": "High",
        "conditions": ["Laundering_type IS NOT EMPTY"],
        "active": True,
    },
    {
        "id": "AML-R006",
        "name": "Rapid Succession Transfers",
        "description": "Flag accounts appearing as sender in 3+ transactions within 1 hour.",
        "severity": "Medium",
        "conditions": ["Sender_account frequency > 3 per hour"],
        "active": False,
    },
]


def _render_step_rules(ds, update_status_fn) -> None:
    """Step 3: Compliance / session rules configuration."""
    _render_step_bar("rules")

    st.markdown(f"### 📐 Compliance Rules — {ds.name}")
    st.caption(
        "Configure rules that define how transactions should be scored during this analysis session. "
        "Enable default rules, adjust severity, or add custom rules."
    )

    # ── Persist rules in session state ────────────
    if "ds_rules" not in st.session_state:
        import copy
        st.session_state["ds_rules"] = copy.deepcopy(_DEFAULT_RULES)

    rules: list[dict] = st.session_state["ds_rules"]

    # ── Active rules summary ──────────────────────
    active_count = sum(1 for r in rules if r["active"])
    high_count = sum(1 for r in rules if r["active"] and r["severity"] == "High")
    med_count = sum(1 for r in rules if r["active"] and r["severity"] == "Medium")
    low_count = sum(1 for r in rules if r["active"] and r["severity"] == "Low")

    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("Total Rules", len(rules))
    sm2.metric("Active", active_count)
    sm3.metric("High Severity", high_count)
    sm4.metric("Medium / Low", f"{med_count} / {low_count}")

    st.markdown("")

    # ── Rule cards grid (2 per row) ───────────────
    st.markdown("#### Existing Rules")
    RULES_PER_ROW = 2
    for row_start in range(0, len(rules), RULES_PER_ROW):
        cols = st.columns(RULES_PER_ROW, gap="medium")
        for col_idx, rule in enumerate(rules[row_start : row_start + RULES_PER_ROW]):
            with cols[col_idx]:
                sev_badge = _risk_badge_html(rule["severity"])
                active_label = (
                    '<span class="ds-badge ds-badge-completed">Active</span>'
                    if rule["active"]
                    else '<span class="ds-badge ds-badge-unknown">Inactive</span>'
                )

                conditions_html = "".join(
                    f'<div style="font-size:0.78rem; color:#94a3b8; padding:1px 0;">• {c}</div>'
                    for c in rule["conditions"]
                )

                st.markdown(
                    f'<div class="rule-card">'
                    f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                    f'<div class="rule-name">{rule["name"]}</div>'
                    f'<div>{sev_badge} {active_label}</div>'
                    f'</div>'
                    f'<div class="rule-id">{rule["id"]}</div>'
                    f'<div class="rule-desc">{rule["description"]}</div>'
                    f'<div style="margin-top:0.4rem;">{conditions_html}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Toggle active state
                rule_idx = row_start + col_idx
                toggle_label = "Deactivate" if rule["active"] else "Activate"
                if st.button(
                    f"{'🔴' if rule['active'] else '🟢'} {toggle_label}",
                    key=f"toggle_rule_{rule['id']}",
                    use_container_width=True,
                ):
                    st.session_state["ds_rules"][rule_idx]["active"] = not rule["active"]
                    st.rerun()

    st.markdown("---")

    # ── Natural Language Rule Builder ─────────────
    st.markdown(
        '<div class="nl-builder">'
        '<div class="nl-builder-header">'
        '<h4>🧠 Natural Language Rule Builder</h4>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="nl-builder-tip">'
        '💡 <strong>Write rules in plain English</strong> — the AI will parse your '
        'description into structured conditions, severity, and parameters automatically.'
        '</div>',
        unsafe_allow_html=True,
    )

    # State keys for the NL builder flow
    NL_STATE = "nl_rule_state"       # "input" | "parsing" | "confirm" | "error"
    NL_TEXT = "nl_rule_text"         # raw user text
    NL_PARSED = "nl_rule_parsed"    # parsed dict from LLM/heuristic
    NL_ERROR = "nl_rule_error"      # error message

    if NL_STATE not in st.session_state:
        st.session_state[NL_STATE] = "input"
    if NL_TEXT not in st.session_state:
        st.session_state[NL_TEXT] = ""

    state = st.session_state[NL_STATE]

    # ── State: INPUT ──────────────────────────────
    if state in ("input", "error"):
        nl_input = st.text_area(
            "Describe your rule",
            value=st.session_state[NL_TEXT],
            placeholder=(
                "e.g., Flag transactions where amount > $10,000 and the destination "
                "country is not in our whitelist.\n\n"
                "e.g., Boost risk score by 15 if an entity has made more than 5 "
                "transfers in the last 24 hours.\n\n"
                "e.g., Alert on any cash deposit over $5,000 routed through high-risk jurisdictions."
            ),
            height=100,
            key="nl_rule_input_area",
            help="Write your compliance rule in natural language. The system will automatically "
                 "extract conditions, severity, and parameters.",
        )

        # Show prior error if in error state
        if state == "error" and NL_ERROR in st.session_state:
            err_msg = st.session_state[NL_ERROR]
            st.markdown(
                f'<div class="nl-error-card">'
                f'<div class="nl-error-text">⚠️ {err_msg}</div>'
                f'<div style="font-size:0.78rem; color:#94a3b8; margin-top:0.3rem;">'
                f'Try rephrasing, or the rule was parsed with heuristics below.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # If we have a heuristic fallback result despite the error, show confirm
            if NL_PARSED in st.session_state and st.session_state[NL_PARSED]:
                st.session_state[NL_STATE] = "confirm"
                st.rerun()

        parse_col, example_col = st.columns([1, 2])
        with parse_col:
            parse_disabled = not (nl_input and nl_input.strip())
            if st.button(
                "🔍 Parse Rule",
                key="nl_parse_btn",
                type="primary",
                use_container_width=True,
                disabled=parse_disabled,
            ):
                st.session_state[NL_TEXT] = nl_input.strip()
                st.session_state[NL_STATE] = "parsing"
                st.rerun()

        with example_col:
            st.markdown(
                '<span style="font-size:0.78rem; color:#64748b;">'
                'Examples: "Flag transactions over $50k to sanctioned countries" · '
                '"Alert when same account sends 3+ transfers in 1 hour" · '
                '"Medium severity for currency mismatch with cash deposits"</span>',
                unsafe_allow_html=True,
            )

    # ── State: PARSING (spinner) ──────────────────
    elif state == "parsing":
        st.markdown(
            f'<div style="padding:0.5rem 0; color:#94a3b8; font-size:0.88rem;">'
            f'Analyzing: <em>"{st.session_state[NL_TEXT][:100]}…"</em></div>',
            unsafe_allow_html=True,
        )
        with st.spinner("🧠 AI is parsing your rule into structured conditions…"):
            parsed = parse_nl_rule_to_structured(st.session_state[NL_TEXT])

        if parsed.get("error"):
            # LLM failed but heuristic may have still produced a result
            error_msg = parsed.pop("error")
            if parsed.get("name"):
                # Heuristic produced a fallback → show with warning
                st.session_state[NL_PARSED] = parsed
                st.session_state[NL_ERROR] = error_msg
                st.session_state[NL_STATE] = "confirm"
            else:
                st.session_state[NL_ERROR] = error_msg
                st.session_state[NL_STATE] = "error"
        else:
            st.session_state[NL_PARSED] = parsed
            st.session_state[NL_STATE] = "confirm"

        st.rerun()

    # ── State: CONFIRM ────────────────────────────
    elif state == "confirm":
        parsed = st.session_state.get(NL_PARSED, {})
        if not parsed:
            st.session_state[NL_STATE] = "input"
            st.rerun()

        source = parsed.get("source", "unknown")
        source_badge = (
            '<span class="nl-source-badge nl-source-llm">🤖 LLM Parsed</span>'
            if source == "llm"
            else '<span class="nl-source-badge nl-source-heuristic">⚙️ Heuristic Parsed</span>'
        )

        sev_badge = _risk_badge_html(parsed.get("severity", "Medium"))
        conditions_html = "".join(
            f'<div class="nl-cond-item">• {c}</div>'
            for c in parsed.get("conditions", [])
        )

        params = parsed.get("parameters", {})
        params_html = ""
        if params:
            params_str = " · ".join(f"{k}={v}" for k, v in params.items())
            params_html = f'<div class="nl-params">📊 Parameters: {params_str}</div>'

        # Show LLM error as warning if present
        if NL_ERROR in st.session_state and st.session_state[NL_ERROR]:
            st.warning(f"⚠️ {st.session_state[NL_ERROR]}", icon="⚠️")

        st.markdown(
            f'<div class="nl-confirm-card">'
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'<h5>✅ Parsed Rule Preview</h5>'
            f'<div>{source_badge}</div>'
            f'</div>'
            f'<div style="display:flex; justify-content:space-between; align-items:center; '
            f'margin-bottom:0.5rem;">'
            f'<div style="font-weight:600; font-size:1rem;">{parsed.get("name", "Custom Rule")}</div>'
            f'<div>{sev_badge}</div>'
            f'</div>'
            f'<div style="font-size:0.85rem; color:#94a3b8; margin-bottom:0.5rem;">'
            f'{parsed.get("description", "")}</div>'
            f'<div style="font-weight:600; font-size:0.82rem; margin-bottom:0.2rem;">Conditions:</div>'
            f'{conditions_html}'
            f'{params_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Editable overrides
        st.markdown("")
        edit_cols = st.columns([2, 1, 1])
        with edit_cols[0]:
            edited_name = st.text_input(
                "Rule Name",
                value=parsed.get("name", "Custom Rule"),
                key="nl_edit_name",
            )
        with edit_cols[1]:
            sev_options = ["High", "Medium", "Low"]
            default_sev = parsed.get("severity", "Medium")
            sev_idx = sev_options.index(default_sev) if default_sev in sev_options else 1
            edited_severity = st.selectbox(
                "Severity",
                sev_options,
                index=sev_idx,
                key="nl_edit_severity",
            )
        with edit_cols[2]:
            edited_id = st.text_input(
                "Rule ID",
                value=f"AML-NL{len(rules)+1:03d}",
                key="nl_edit_id",
            )

        # Action buttons
        btn_accept, btn_edit, btn_discard = st.columns(3)
        with btn_accept:
            if st.button(
                "✅ Accept & Save Rule",
                key="nl_accept_btn",
                type="primary",
                use_container_width=True,
            ):
                new_rule = {
                    "id": edited_id.strip() or f"AML-NL{len(rules)+1:03d}",
                    "name": edited_name.strip() or parsed.get("name", "Custom NL Rule"),
                    "description": parsed.get("description", st.session_state.get(NL_TEXT, "")),
                    "severity": edited_severity,
                    "conditions": parsed.get("conditions", []),
                    "active": True,
                    "source": source,
                    "parameters": params,
                }
                st.session_state["ds_rules"].append(new_rule)
                # Reset NL builder state
                st.session_state[NL_STATE] = "input"
                st.session_state[NL_TEXT] = ""
                st.session_state.pop(NL_PARSED, None)
                st.session_state.pop(NL_ERROR, None)
                st.success(f"✅ Rule **{new_rule['name']}** added to active rules.")
                st.rerun()

        with btn_edit:
            if st.button(
                "✏️ Re-write Rule",
                key="nl_rewrite_btn",
                use_container_width=True,
            ):
                st.session_state[NL_STATE] = "input"
                st.session_state.pop(NL_PARSED, None)
                st.session_state.pop(NL_ERROR, None)
                st.rerun()

        with btn_discard:
            if st.button(
                "🗑️ Discard",
                key="nl_discard_btn",
                use_container_width=True,
            ):
                st.session_state[NL_STATE] = "input"
                st.session_state[NL_TEXT] = ""
                st.session_state.pop(NL_PARSED, None)
                st.session_state.pop(NL_ERROR, None)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Inject active rules into session rule store ─
    st.markdown("---")

    # ── Bottom navigation ─────────────────────────
    nav_l, nav_center, nav_r = st.columns([1, 2, 1])
    with nav_l:
        if st.button("← Back to Validation", key="rules_back", use_container_width=True):
            st.session_state["ds_flow_step"] = "validate"
            st.rerun()
    with nav_center:
        active_rules = [r for r in rules if r["active"]]
        st.markdown(
            f'<div style="text-align:center; color:#64748b; padding-top:0.4rem;">'
            f'{len(active_rules)} active rule(s) will be applied during scoring</div>',
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button(
            "🚀 Start Analysis",
            key="rules_start",
            type="primary",
            use_container_width=True,
        ):
            # Inject rules into session rule store
            rule_store = get_rule_store()
            rule_store.clear()
            parsed_rules = [
                Rule(
                    rule_type=r["severity"].lower(),
                    description=f"[{r['id']}] {r['name']}: {'; '.join(r['conditions'])}",
                )
                for r in active_rules
            ]
            rule_store.add_rules(parsed_rules)
            set_session_rules(rule_store.get_rules())

            update_status_fn(ds.dataset_id, "Completed")
            st.session_state["ds_flow_step"] = "analysis"
            # Keep ds_analysis_id set so analysis step knows the dataset
            st.success(
                f"✅ Analysis configured with {len(active_rules)} rules. "
                f"Opening analysis dashboard…"
            )
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Per-Dataset Analysis (Risk Analysis + Data Query Assistant)
# ══════════════════════════════════════════════════════════════════════════════


def _render_step_analysis(ds) -> None:
    """Step 4: Per-dataset analysis dashboard with Risk Analysis and Data Query Assistant sub-tabs."""
    _render_step_bar("analysis")

    # ── Header with dataset context ───────────────
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown(f"### ⚡ Analysis — {ds.name}")
        st.caption(
            f"{ds.total_rows:,} transactions · {ds.fraud_pct} fraud · "
            f"Risk Level: {ds.risk_level} · Status: {ds.status}"
        )
    with hdr_r:
        if st.button("← Back to Datasets", key="analysis_back_overview", use_container_width=True):
            st.session_state["ds_flow_step"] = "overview"
            st.session_state["ds_analysis_id"] = None
            st.rerun()

    st.markdown("")

    # ── Load the dataset ──────────────────────────
    ds_path = Path(ds.file_path)
    df = None
    if ds_path.exists():
        try:
            suffix = ds_path.suffix.lower()
            df = pd.read_excel(ds_path) if suffix in (".xls", ".xlsx") else pd.read_csv(ds_path)
        except Exception as exc:
            st.error(f"Failed to load dataset: {exc}")
            return
    else:
        st.error(f"Dataset file not found: {ds.file_path}")
        return

    # ── ML scoring pass (if trained model exists) ─────────────
    ml_scoring_meta: dict[str, str | float | int | bool] = {
        "enabled": False,
        "threshold": 0.5,
    }
    try:
        with st.spinner("Running ML scoring on uploaded dataset..."):
            df, ml_scoring_meta = _score_dataset_with_ml(df)
    except Exception as exc:
        st.warning(f"ML scoring skipped due to error: {exc}")

    # ── Sub-tabs: Risk Analysis + Data Query Assistant ──
    ra_tab, dqa_tab = st.tabs(["⚡ Risk Analysis", "💬 Data Query Assistant"])

    rule_store = get_rule_store()

    with ra_tab:
        section_risk_analysis(df, ds, ml_scoring_meta)

    with dqa_tab:
        section_ai_chat(rule_store)




# ── Combined Tab Wrappers ────────────────────────────────────────────────────


def _build_aml_inference_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build model features from AML-CFT dataset schema for ML inference."""
    lower_to_original = {col.strip().lower(): col for col in df.columns}

    direct_feature_cols = {
        "transaction_amount",
        "tx_count_last_hour",
        "has_upi",
        "nlp_signal",
    }
    if direct_feature_cols.issubset(set(lower_to_original.keys())):
        feature_df = pd.DataFrame()
        feature_df["transaction_amount"] = pd.to_numeric(
            df[lower_to_original["transaction_amount"]], errors="coerce"
        )
        feature_df["tx_count_last_hour"] = pd.to_numeric(
            df[lower_to_original["tx_count_last_hour"]], errors="coerce"
        )
        feature_df["has_upi"] = pd.to_numeric(
            df[lower_to_original["has_upi"]], errors="coerce"
        ).fillna(0)
        feature_df["nlp_signal"] = pd.to_numeric(
            df[lower_to_original["nlp_signal"]], errors="coerce"
        ).fillna(0)
        return feature_df

    required = {
        "time",
        "date",
        "sender_account",
        "amount",
        "payment_currency",
        "received_currency",
        "sender_bank_location",
        "receiver_bank_location",
        "payment_type",
        "laundering_type",
    }
    if not required.issubset(set(lower_to_original.keys())):
        raise ValueError("Dataset does not include required AML-CFT columns for ML inference.")

    date_col = lower_to_original["date"]
    time_col = lower_to_original["time"]
    sender_col = lower_to_original["sender_account"]
    amount_col = lower_to_original["amount"]
    payment_curr_col = lower_to_original["payment_currency"]
    received_curr_col = lower_to_original["received_currency"]
    sender_loc_col = lower_to_original["sender_bank_location"]
    receiver_loc_col = lower_to_original["receiver_bank_location"]
    payment_type_col = lower_to_original["payment_type"]
    laundering_type_col = lower_to_original["laundering_type"]

    combined_ts = pd.to_datetime(
        df[date_col].astype(str).str.strip() + " " + df[time_col].astype(str).str.strip(),
        errors="coerce",
    )
    hour_bucket = combined_ts.dt.floor("h")

    feature_df = pd.DataFrame(index=df.index)
    feature_df["transaction_amount"] = pd.to_numeric(df[amount_col], errors="coerce")
    feature_df["tx_count_last_hour"] = (
        df.groupby([df[sender_col], hour_bucket])[amount_col].transform("count")
    )
    feature_df["has_upi"] = df[sender_col].notna().astype(int)

    payment_type_risk = (
        df[payment_type_col]
        .astype(str)
        .str.lower()
        .map(
            {
                "cross-border": 30.0,
                "cash deposit": 18.0,
                "cheque": 12.0,
                "ach": 10.0,
                "credit card": 8.0,
                "debit card": 6.0,
            }
        )
        .fillna(5.0)
    )

    cross_currency = (
        df[payment_curr_col].astype(str).str.lower().str.strip()
        != df[received_curr_col].astype(str).str.lower().str.strip()
    ).astype(float) * 20.0

    cross_border = (
        df[sender_loc_col].astype(str).str.lower().str.strip()
        != df[receiver_loc_col].astype(str).str.lower().str.strip()
    ).astype(float) * 22.0

    laundering_text_score = (
        df[laundering_type_col]
        .astype(str)
        .str.lower()
        .str.contains("fan_out|fan-in|fan_in|group|layer|cross", regex=True)
        .astype(float)
        * 18.0
    )

    feature_df["nlp_signal"] = (
        payment_type_risk + cross_currency + cross_border + laundering_text_score
    ).clip(0.0, 100.0)

    return feature_df


def _score_dataset_with_ml(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run trained model inference on uploaded dataset and return scored dataframe."""
    from app.core.config import CONFIG

    ml_meta = _get_ml_metadata_dict()
    threshold = float(ml_meta.get("threshold", 0.5))
    scored = df.copy()

    if not MODEL_PATH.exists():
        return scored, {
            "enabled": False,
            "reason": "No trained model artifact found.",
            "threshold": threshold,
        }

    try:
        import joblib

        model = joblib.load(MODEL_PATH)
        features = _build_aml_inference_features(scored)
        feature_cols = ["transaction_amount", "tx_count_last_hour", "has_upi", "nlp_signal"]
        features = features[feature_cols].fillna(0.0)

        probabilities = model.predict_proba(features)[:, 1]
        scored["ml_probability"] = pd.Series(probabilities, index=scored.index).round(6)
        scored["ml_score"] = (scored["ml_probability"] * 100.0).round(2)
        scored["ml_flag"] = (scored["ml_probability"] >= threshold).astype(int)
        scored["risk_band"] = pd.cut(
            scored["ml_score"],
            bins=[-0.01, 40.0, 70.0, 100.0],
            labels=["Low", "Medium", "High"],
        ).astype(str)

        amount_signal = (features["transaction_amount"] / 100_000.0).clip(0.0, 1.0)
        velocity_signal = (features["tx_count_last_hour"] / 10.0).clip(0.0, 1.0)
        pattern_signal = (features["nlp_signal"] / 100.0).clip(0.0, 1.0)
        dominant = pd.DataFrame(
            {
                "amount": amount_signal,
                "velocity": velocity_signal,
                "pattern": pattern_signal,
            }
        ).idxmax(axis=1)
        scored["ml_explanation"] = dominant.map(
            {
                "amount": "High amount profile",
                "velocity": "High transaction velocity",
                "pattern": "Cross-border/pattern signal",
            }
        )

        # ── RAW proxy score (batch approximation of deterministic guardrails) ──
        amount_series = scored["Amount"] if "Amount" in scored.columns else pd.Series(0.0, index=scored.index)
        amount_vals = pd.to_numeric(amount_series, errors="coerce").fillna(0.0)
        velocity_vals = pd.to_numeric(features["tx_count_last_hour"], errors="coerce").fillna(0.0)
        sender_series = scored["Sender_account"] if "Sender_account" in scored.columns else pd.Series("", index=scored.index)
        receiver_series = scored["Receiver_account"] if "Receiver_account" in scored.columns else pd.Series("", index=scored.index)
        sender_loc_series = scored["Sender_bank_location"] if "Sender_bank_location" in scored.columns else pd.Series("", index=scored.index)
        receiver_loc_series = scored["Receiver_bank_location"] if "Receiver_bank_location" in scored.columns else pd.Series("", index=scored.index)

        sender_missing = sender_series.astype(str).str.strip().eq("")
        cross_border_ind = (
            sender_loc_series.astype(str).str.lower().str.strip()
            != receiver_loc_series.astype(str).str.lower().str.strip()
        ).astype(float)
        round_amount_ind = ((amount_vals > 0) & ((amount_vals % 1000.0) == 0)).astype(float)

        raw_score = (
            (velocity_vals >= float(CONFIG.velocity_threshold_per_hour)).astype(float) * 32.0
            + (amount_vals >= float(CONFIG.high_amount_threshold)).astype(float) * 30.0
            + sender_missing.astype(float) * 18.0
            + cross_border_ind * 12.0
            + round_amount_ind * 8.0
        ).clip(0.0, 100.0)
        scored["raw_score_proxy"] = raw_score.round(2)

        # ── GRAPH proxy score (fan-out/fan-in + corridor anomaly approximation) ──
        sender_col = sender_series.astype(str)
        receiver_col = receiver_series.astype(str)
        sender_out_degree = receiver_col.groupby(sender_col).transform("nunique")
        receiver_in_degree = sender_col.groupby(receiver_col).transform("nunique")

        sender_out_norm = (pd.to_numeric(sender_out_degree, errors="coerce").fillna(0.0) / 15.0).clip(0.0, 1.0)
        receiver_in_norm = (pd.to_numeric(receiver_in_degree, errors="coerce").fillna(0.0) / 25.0).clip(0.0, 1.0)
        graph_score = (sender_out_norm * 45.0 + receiver_in_norm * 45.0 + cross_border_ind * 10.0).clip(0.0, 100.0)
        scored["graph_score_proxy"] = graph_score.round(2)

        # ── Final composite score aligned with 3-layer formula ──
        final_score = (
            float(CONFIG.raw_weight) * scored["raw_score_proxy"]
            + float(CONFIG.ml_weight) * scored["ml_score"]
            + float(CONFIG.graph_weight) * scored["graph_score_proxy"]
        ).clip(0.0, float(CONFIG.max_score))
        scored["final_risk_score"] = final_score.round(2)
        scored["final_exposure"] = pd.cut(
            scored["final_risk_score"],
            bins=[-0.01, float(CONFIG.medium_risk_threshold), float(CONFIG.high_risk_threshold), float(CONFIG.max_score)],
            labels=["Low", "Medium", "High"],
        ).astype(str)

        return scored, {
            "enabled": True,
            "threshold": threshold,
            "rows_scored": int(len(scored)),
            "high_risk_rows": int((scored["risk_band"] == "High").sum()),
            "avg_ml_score": float(scored["ml_score"].mean()) if len(scored) else 0.0,
            "avg_final_score": float(scored["final_risk_score"].mean()) if len(scored) else 0.0,
            "high_final_rows": int((scored["final_exposure"] == "High").sum()),
            "model_type": ml_meta.get("model_type", "Trained model"),
        }
    except Exception as exc:
        return scored, {
            "enabled": False,
            "reason": f"ML scoring failed: {exc}",
            "threshold": threshold,
        }


def _ra_metric_card_html(
    label: str, value: str, trend: str = "", trend_dir: str = "flat", color: str = "#e2e8f0"
) -> str:
    """Render one summary metric card."""
    trend_html = ""
    if trend:
        arrow = "↑" if trend_dir == "up" else ("↓" if trend_dir == "down" else "→")
        trend_html = f'<div class="ra-metric-trend {trend_dir}">{arrow} {trend}</div>'
    return (
        f'<div class="ra-metric-card">'
        f'<div class="ra-metric-label">{label}</div>'
        f'<div class="ra-metric-value" style="color:{color};">{value}</div>'
        f'{trend_html}'
        f'</div>'
    )


def _ra_risk_meter_svg(score: float, size: int = 90) -> str:
    """Compact SVG risk meter gauge."""
    pct = min(max(score / 100.0, 0.0), 1.0)
    r = int(size * 0.42)
    circ = 2 * 3.14159 * r
    offset = circ * (1 - pct)
    color = "#ef4444" if pct >= 0.7 else ("#f59e0b" if pct >= 0.4 else "#22c55e")
    label = "HIGH" if pct >= 0.7 else ("MED" if pct >= 0.4 else "LOW")
    cx = size // 2
    return (
        f'<div style="text-align:center;">'
        f'<div style="position:relative; display:inline-block; width:{size}px; height:{size}px;">'
        f'<svg width="{size}" height="{size}" style="transform:rotate(-90deg);">'
        f'<circle cx="{cx}" cy="{cx}" r="{r}" stroke="rgba(120,120,120,0.15)" '
        f'stroke-width="7" fill="none"/>'
        f'<circle cx="{cx}" cy="{cx}" r="{r}" stroke="{color}" '
        f'stroke-width="7" fill="none" stroke-linecap="round" '
        f'stroke-dasharray="{circ}" stroke-dashoffset="{offset:.1f}"/>'
        f'</svg>'
        f'<div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); '
        f'font-size:1.3rem; font-weight:700; color:{color};">{score:.0f}</div>'
        f'</div>'
        f'<div style="font-size:0.75rem; color:#94a3b8; margin-top:0.15rem;">{label} RISK</div>'
        f'</div>'
    )


def _ra_get_llm_dataset_insight(df: pd.DataFrame, ds_record, rule_store) -> str:
    """Generate an LLM-driven narrative insight from the actual dataset, with heuristic fallback."""
    import os

    has_fraud_col = "Is_laundering" in df.columns
    fraud_count = int(df["Is_laundering"].sum()) if has_fraud_col else 0
    total = len(df)
    fraud_pct = (fraud_count / total * 100) if total else 0

    has_type_col = "Laundering_type" in df.columns
    top_types = ""
    if has_type_col:
        fraud_rows = df[df["Is_laundering"] == 1] if has_fraud_col else df
        if not fraud_rows.empty:
            top_types = ", ".join(
                f"{t}({c})" for t, c in fraud_rows["Laundering_type"].value_counts().head(5).items()
            )

    has_amount = "Amount" in df.columns
    avg_amount = df["Amount"].mean() if has_amount else 0
    max_amount = df["Amount"].max() if has_amount else 0
    cross_border = int((df["Payment_type"] == "Cross-border").sum()) if "Payment_type" in df.columns else 0
    cross_pct = cross_border / total * 100 if total else 0

    unique_senders = df["Sender_account"].nunique() if "Sender_account" in df.columns else 0
    unique_receivers = df["Receiver_account"].nunique() if "Receiver_account" in df.columns else 0

    data_summary = (
        f"Dataset: {ds_record.name}, {total:,} transactions. "
        f"Fraud: {fraud_count} ({fraud_pct:.2f}%). "
        f"Avg amount: {avg_amount:,.0f}, Max: {max_amount:,.0f}. "
        f"Cross-border: {cross_border} ({cross_pct:.1f}%). "
        f"Unique senders: {unique_senders:,}, receivers: {unique_receivers:,}. "
        f"Top fraud types: {top_types}."
    )

    ml_summary = _get_ml_artifacts_summary()

    llm_disabled = os.getenv("AEGIS_LLM_ENABLED", "").lower() in {"0", "false", "no", "off"}
    if not llm_disabled:
        try:
            from app.services.session_rules import chat_with_rules as _cwr
            active_rules = rule_store.get_rules() if rule_store else []
            raw = _cwr(
                user_message=(
                    "Provide a concise 4-5 sentence analyst briefing about this AML transaction dataset. "
                    "Highlight patterns, suspicious clusters, cross-border risk, and laundering typologies. "
                    "Be specific with numbers and percentages."
                ),
                session_rules=active_rules,
                system_context=(
                    "You are a senior AML risk analyst. Provide a brief narrative insight. "
                    f"Dataset details: {data_summary} "
                    f"ML info: {ml_summary}"
                ),
                ml_artifacts=ml_summary,
            )
            sections = format_llm_response(raw)
            if sections.get("result"):
                return sections["result"]
        except Exception:
            pass

    # Heuristic fallback
    insight = (
        f"**Dataset Overview:** Analysed **{total:,}** transactions with a "
        f"fraud rate of **{fraud_pct:.2f}%** ({fraud_count:,} flagged). "
    )
    if cross_pct > 5:
        insight += f"Cross-border transactions represent **{cross_pct:.1f}%** of all activity — elevated geographic risk. "
    if fraud_count > 0 and top_types:
        insight += f"Primary laundering typologies detected: {top_types}. "
    if avg_amount > 10000:
        insight += f"Average transaction amount is high ({avg_amount:,.0f}), indicating large-value transfer patterns. "
    insight += (
        f"Network spans **{unique_senders:,}** sender accounts → **{unique_receivers:,}** receiver accounts."
    )
    return insight


def section_risk_analysis(df: pd.DataFrame, ds_record, ml_scoring_meta: dict | None = None) -> None:
    """Risk Analysis Dashboard — analyses the actual dataset from the file."""
    rule_store = get_rule_store()

    # ── Column detection ─────────────────────────
    has_fraud = "Is_laundering" in df.columns
    has_amount = "Amount" in df.columns
    has_type = "Laundering_type" in df.columns
    has_payment = "Payment_type" in df.columns
    has_sender = "Sender_account" in df.columns
    has_receiver = "Receiver_account" in df.columns
    has_sender_loc = "Sender_bank_location" in df.columns
    has_receiver_loc = "Receiver_bank_location" in df.columns
    has_currency = "Payment_currency" in df.columns
    has_date = "Date" in df.columns
    has_ml_score = "ml_score" in df.columns
    has_final_score = "final_risk_score" in df.columns

    if ml_scoring_meta and ml_scoring_meta.get("enabled") and has_ml_score:
        st.caption(
            f"🤖 ML scoring enabled · {int(ml_scoring_meta.get('rows_scored', len(df))):,} rows scored · "
            f"Avg ML score {float(ml_scoring_meta.get('avg_ml_score', 0.0)):.1f} · "
            f"Threshold {float(ml_scoring_meta.get('threshold', 0.5)):.2f}"
        )
        if has_final_score:
            st.caption(
                f"🛡️ Composite risk (RAW+ML+GRAPH proxies) · "
                f"Avg {float(ml_scoring_meta.get('avg_final_score', 0.0)):.1f} · "
                f"High exposure rows {int(ml_scoring_meta.get('high_final_rows', 0)):,}"
            )
    elif ml_scoring_meta and not ml_scoring_meta.get("enabled"):
        st.caption(f"🤖 ML scoring unavailable: {ml_scoring_meta.get('reason', 'Unknown reason')}")

    # ── 1. Search & Export Bar ───────────────────
    hdr_c1, hdr_c2, hdr_c3 = st.columns([3, 1, 0.8])
    with hdr_c1:
        search_query = st.text_input(
            "🔍 Search accounts, amounts, types…",
            key="ra_search",
            placeholder="e.g. 8724731955, Cross-border, Structuring",
            label_visibility="collapsed",
        )
    with hdr_c2:
        export_fmt = st.selectbox(
            "Export", ["Excel/CSV", "Text Summary", "SAR Draft"],
            key="ra_export_fmt", label_visibility="collapsed",
        )
    with hdr_c3:
        export_clicked = st.button("📥 Export", key="ra_export_btn", use_container_width=True)

    # Apply search filter
    filtered_df = df.copy()
    if search_query:
        q = search_query.lower()
        searchable_cols = [
            c for c in [
                "Sender_account", "Receiver_account", "Payment_type", "Laundering_type",
                "Sender_bank_location", "Receiver_bank_location", "Payment_currency", "Received_currency",
            ] if c in filtered_df.columns
        ]
        if searchable_cols:
            combined = filtered_df[searchable_cols].astype(str).agg(" ".join, axis=1).str.lower()
            mask = combined.str.contains(q, na=False)
        else:
            mask = filtered_df.astype(str).agg(" ".join, axis=1).str.lower().str.contains(q, na=False)
        filtered_df = filtered_df[mask]
        if len(filtered_df) < len(df):
            st.caption(f"🔍 Showing {len(filtered_df):,} of {len(df):,} transactions matching \"{search_query}\"")

    # Handle export
    if export_clicked:
        if export_fmt == "Excel/CSV":
            csv_data = filtered_df.to_csv(index=False)
            st.download_button(
                "⬇ Download CSV", data=csv_data,
                file_name=f"aegis_{ds_record.name}_export.csv", mime="text/csv",
                key="ra_dl_csv",
            )
        elif export_fmt == "Text Summary":
            fraud_c = int(filtered_df["Is_laundering"].sum()) if has_fraud else 0
            lines = [
                f"AEGIS-AML Analysis Report — {ds_record.name}",
                "=" * 50,
                f"Total Transactions: {len(filtered_df):,}",
                f"Fraud Flagged: {fraud_c:,}",
                f"Fraud Rate: {fraud_c / len(filtered_df) * 100:.2f}%" if len(filtered_df) else "",
                f"Amount Range: {filtered_df['Amount'].min():,.2f} – {filtered_df['Amount'].max():,.2f}" if has_amount else "",
                "",
            ]
            st.download_button(
                "⬇ Download Summary", data="\n".join(lines),
                file_name=f"aegis_{ds_record.name}_summary.txt", mime="text/plain",
                key="ra_dl_txt",
            )
        else:
            st.info("Select an entity below to generate a SAR draft.")

    # ── 2. Summary Metric Cards ──────────────────
    total_txns = len(filtered_df)
    fraud_count = int(filtered_df["Is_laundering"].sum()) if has_fraud else 0
    legit_count = total_txns - fraud_count
    fraud_rate = (fraud_count / total_txns * 100) if total_txns else 0
    cross_border = int((filtered_df["Payment_type"] == "Cross-border").sum()) if has_payment else 0
    avg_amount = filtered_df["Amount"].mean() if has_amount and total_txns else 0
    unique_entities = filtered_df["Sender_account"].nunique() if has_sender else 0

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1:
        st.markdown(
            _ra_metric_card_html("Transactions", f"{total_txns:,}", f"{legit_count:,} legit", "flat"),
            unsafe_allow_html=True,
        )
    with mc2:
        st.markdown(
            _ra_metric_card_html(
                "Fraud Flagged", f"{fraud_count:,}",
                f"{fraud_rate:.2f}%",
                "up" if fraud_rate > 1 else "flat",
                "#ef4444" if fraud_count > 0 else "#22c55e",
            ),
            unsafe_allow_html=True,
        )
    with mc3:
        st.markdown(
            _ra_metric_card_html(
                "Cross-Border", f"{cross_border:,}",
                f"{cross_border / total_txns * 100:.1f}%" if total_txns else "0%",
                "up" if cross_border > total_txns * 0.1 else "flat",
                "#f59e0b",
            ),
            unsafe_allow_html=True,
        )
    with mc4:
        st.markdown(
            _ra_metric_card_html("Avg Amount", f"{avg_amount:,.0f}", "", "flat", "#3b82f6"),
            unsafe_allow_html=True,
        )
    with mc5:
        st.markdown(
            _ra_metric_card_html("Unique Entities", f"{unique_entities:,}", "", "flat", "#8b5cf6"),
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── 3. Charts Row ────────────────────────────
    chart_c1, chart_c2 = st.columns(2, gap="medium")

    with chart_c1:
        st.markdown('<div class="ra-panel">', unsafe_allow_html=True)
        if has_fraud and has_type:
            st.markdown("<h5>🔴 Laundering Typology Breakdown</h5>", unsafe_allow_html=True)
            fraud_df = filtered_df[filtered_df["Is_laundering"] == 1]
            if not fraud_df.empty:
                type_counts = fraud_df["Laundering_type"].value_counts().head(10)
                chart_df = type_counts.reset_index()
                chart_df.columns = ["Typology", "Count"]
                st.bar_chart(chart_df.set_index("Typology"), height=260)
            else:
                st.info("No fraud-flagged transactions in the current filter.")
        elif has_payment:
            st.markdown("<h5>💳 Payment Type Distribution</h5>", unsafe_allow_html=True)
            pt_counts = filtered_df["Payment_type"].value_counts()
            chart_df = pt_counts.reset_index()
            chart_df.columns = ["Type", "Count"]
            st.bar_chart(chart_df.set_index("Type"), height=260)
        st.markdown('</div>', unsafe_allow_html=True)

    with chart_c2:
        st.markdown('<div class="ra-panel">', unsafe_allow_html=True)
        if has_amount:
            st.markdown("<h5>💰 Transaction Amount Distribution</h5>", unsafe_allow_html=True)
            import numpy as np
            amounts = filtered_df["Amount"].dropna()
            bins = [0, 100, 500, 1000, 5000, 10000, 50000, 100000, float("inf")]
            labels = ["<100", "100-500", "500-1K", "1K-5K", "5K-10K", "10K-50K", "50K-100K", ">100K"]
            bucketed = pd.cut(amounts, bins=bins, labels=labels, right=False)
            buck_counts = bucketed.value_counts().reindex(labels, fill_value=0)
            chart_df = buck_counts.reset_index()
            chart_df.columns = ["Range", "Count"]
            st.bar_chart(chart_df.set_index("Range"), height=260)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 4. Second chart row: Geographic + Temporal ─
    chart_c3, chart_c4 = st.columns(2, gap="medium")

    with chart_c3:
        st.markdown('<div class="ra-panel">', unsafe_allow_html=True)
        if has_sender_loc and has_receiver_loc:
            st.markdown("<h5>🌍 Top Geographic Corridors</h5>", unsafe_allow_html=True)
            corridors = (
                filtered_df
                .groupby(["Sender_bank_location", "Receiver_bank_location"])
                .size()
                .reset_index(name="Count")
                .sort_values("Count", ascending=False)
                .head(10)
            )
            corridors["Corridor"] = corridors["Sender_bank_location"] + " → " + corridors["Receiver_bank_location"]
            st.bar_chart(corridors.set_index("Corridor")["Count"], height=260)
        st.markdown('</div>', unsafe_allow_html=True)

    with chart_c4:
        st.markdown('<div class="ra-panel">', unsafe_allow_html=True)
        if has_date:
            st.markdown("<h5>📅 Daily Transaction Volume</h5>", unsafe_allow_html=True)
            daily = filtered_df.groupby("Date").size().reset_index(name="Transactions")
            daily = daily.sort_values("Date")
            if has_fraud:
                daily_fraud = filtered_df[filtered_df["Is_laundering"] == 1].groupby("Date").size().reset_index(name="Fraud")
                daily = daily.merge(daily_fraud, on="Date", how="left").fillna(0)
                daily["Fraud"] = daily["Fraud"].astype(int)
            st.area_chart(daily.set_index("Date"), height=260)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 5. Transaction Table + Entity Panel ──────
    st.markdown("")
    table_col, entity_col = st.columns([1.6, 1], gap="medium")

    with table_col:
        st.markdown('<div class="ra-panel"><h5>📋 Transaction Explorer</h5>', unsafe_allow_html=True)

        # Filter controls
        flt1, flt2, flt3 = st.columns(3)
        with flt1:
            if has_fraud:
                fraud_filter = st.selectbox(
                    "Status", ["All", "Fraud Only", "Legit Only"],
                    key="ra_fraud_filter",
                )
            else:
                fraud_filter = "All"
        with flt2:
            if has_payment:
                pt_options = ["All"] + sorted(filtered_df["Payment_type"].unique().tolist())
                payment_filter = st.selectbox("Payment Type", pt_options, key="ra_pt_filter")
            else:
                payment_filter = "All"
        with flt3:
            if has_amount:
                amount_thresh = st.number_input(
                    "Min Amount", min_value=0.0, value=0.0, step=1000.0, key="ra_amt_filter"
                )
            else:
                amount_thresh = 0.0

        # Apply table filters
        table_df = filtered_df.copy()
        if fraud_filter == "Fraud Only" and has_fraud:
            table_df = table_df[table_df["Is_laundering"] == 1]
        elif fraud_filter == "Legit Only" and has_fraud:
            table_df = table_df[table_df["Is_laundering"] == 0]
        if payment_filter != "All" and has_payment:
            table_df = table_df[table_df["Payment_type"] == payment_filter]
        if amount_thresh > 0 and has_amount:
            table_df = table_df[table_df["Amount"] >= amount_thresh]

        # Select display columns
        display_cols = [c for c in [
            "Sender_account", "Receiver_account", "Amount", "Payment_type",
            "Payment_currency", "Is_laundering", "Laundering_type",
            "ml_score", "risk_band", "ml_flag", "ml_explanation",
            "raw_score_proxy", "graph_score_proxy", "final_risk_score", "final_exposure",
            "Sender_bank_location", "Receiver_bank_location", "Date", "Time",
        ] if c in table_df.columns]

        show_df = table_df[display_cols].head(100)

        # Entity selector from fraud accounts
        entity_options = ["(none)"]
        if has_sender and has_fraud:
            # Prioritize entities with fraud flags
            fraud_senders = table_df[table_df["Is_laundering"] == 1]["Sender_account"].astype(str).unique().tolist() if has_fraud else []
            other_senders = table_df["Sender_account"].astype(str).unique().tolist()[:100]
            seen = set()
            for s in fraud_senders + other_senders:
                if s not in seen:
                    entity_options.append(s)
                    seen.add(s)
                if len(entity_options) > 200:
                    break
        elif has_sender:
            entity_options += sorted(table_df["Sender_account"].astype(str).unique().tolist()[:200])
        selected_entity = st.selectbox(
            "Select entity for deep analysis",
            entity_options,
            key="ra_selected_entity",
        )

        st.dataframe(show_df, use_container_width=True, height=400)

        if len(table_df) > 100:
            st.caption(f"Showing 100 of {len(table_df):,} transactions. Use filters or search to narrow.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Entity Analysis Panel ────────────────────
    with entity_col:
        entity_id = selected_entity if selected_entity != "(none)" else None

        st.markdown('<div class="ra-entity-card">', unsafe_allow_html=True)
        if entity_id and has_sender:
            # Gather all transactions where entity appears as sender or receiver
            is_sender = filtered_df["Sender_account"].astype(str) == entity_id
            is_receiver = filtered_df["Receiver_account"].astype(str) == entity_id if has_receiver else pd.Series(False, index=filtered_df.index)
            entity_txns = filtered_df[is_sender | is_receiver]

            if entity_txns.empty:
                st.markdown(f'<h5>🎯 Entity: {entity_id}</h5>', unsafe_allow_html=True)
                st.caption("No transactions found for this entity.")
            else:
                e_total = len(entity_txns)
                e_fraud = int(entity_txns["Is_laundering"].sum()) if has_fraud else 0
                e_fraud_pct = e_fraud / e_total * 100 if e_total else 0
                e_amount_total = entity_txns["Amount"].sum() if has_amount else 0
                e_amount_avg = entity_txns["Amount"].mean() if has_amount else 0
                sent_count = int(is_sender.sum())
                recv_count = int(is_receiver.sum())
                if "final_risk_score" in entity_txns.columns:
                    e_risk_score = float(entity_txns["final_risk_score"].max())
                elif "ml_score" in entity_txns.columns:
                    e_risk_score = float(entity_txns["ml_score"].max())
                else:
                    e_risk_score = min(100, e_fraud_pct * 10 + (30 if e_fraud > 0 else 0))

                st.markdown(f'<h5>🎯 Entity: {entity_id}</h5>', unsafe_allow_html=True)
                st.markdown(_ra_risk_meter_svg(e_risk_score), unsafe_allow_html=True)

                st.markdown(
                    f'<div class="ra-violation-row">'
                    f'<span class="ra-violation-label">Total Transactions</span>'
                    f'<span class="ra-violation-pts medium">{e_total:,}</span>'
                    f'</div>'
                    f'<div class="ra-violation-row">'
                    f'<span class="ra-violation-label">Sent / Received</span>'
                    f'<span class="ra-violation-pts medium">{sent_count} / {recv_count}</span>'
                    f'</div>'
                    f'<div class="ra-violation-row">'
                    f'<span class="ra-violation-label">Total Volume</span>'
                    f'<span class="ra-violation-pts medium">{e_amount_total:,.0f}</span>'
                    f'</div>'
                    f'<div class="ra-violation-row">'
                    f'<span class="ra-violation-label">Avg Transaction</span>'
                    f'<span class="ra-violation-pts medium">{e_amount_avg:,.0f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if has_fraud:
                    fraud_cls = "high" if e_fraud > 0 else "low"
                    st.markdown(
                        f'<div class="ra-violation-row">'
                        f'<span class="ra-violation-label">Fraud Flagged</span>'
                        f'<span class="ra-violation-pts {fraud_cls}">{e_fraud} ({e_fraud_pct:.1f}%)</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Counterparties
                if has_receiver:
                    counterparties = (
                        entity_txns[is_sender]["Receiver_account"].value_counts().head(5)
                        if sent_count > 0 else pd.Series(dtype=int)
                    )
                    if not counterparties.empty:
                        st.markdown("**Top Counterparties:**")
                        for acct, cnt in counterparties.items():
                            st.markdown(
                                f'<div class="ra-violation-row">'
                                f'<span class="ra-violation-label">{acct}</span>'
                                f'<span class="ra-violation-pts medium">{cnt} txn(s)</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                # Laundering types for this entity
                if has_fraud and has_type and e_fraud > 0:
                    st.markdown("**Laundering Types:**")
                    entity_fraud = entity_txns[entity_txns["Is_laundering"] == 1]
                    for lt, cnt in entity_fraud["Laundering_type"].value_counts().head(4).items():
                        st.markdown(
                            f'<div class="ra-violation-row">'
                            f'<span class="ra-violation-label">{lt}</span>'
                            f'<span class="ra-violation-pts high">{cnt}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                # Geographic spread
                if has_sender_loc:
                    locations = entity_txns["Sender_bank_location"].value_counts()
                    if has_receiver_loc:
                        locations = pd.concat([locations, entity_txns["Receiver_bank_location"].value_counts()])
                        locations = locations.groupby(locations.index).sum().sort_values(ascending=False)
                    if len(locations) > 1:
                        st.markdown("**Geographic Spread:**")
                        for loc, cnt in locations.head(4).items():
                            st.markdown(
                                f'<div class="ra-violation-row">'
                                f'<span class="ra-violation-label">{loc}</span>'
                                f'<span class="ra-violation-pts medium">{cnt}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
        else:
            st.markdown('<h5>🎯 Entity Analysis</h5>', unsafe_allow_html=True)
            st.markdown(
                '<div style="color:#64748b; font-size:0.85rem; padding:1rem 0;">'
                'Select an entity from the table to view transaction profile, '
                'counterparties, risk indicators, and geographic spread.</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Recommended Actions ──────────────────
        st.markdown('<div class="ra-panel" style="margin-top:0.8rem;">', unsafe_allow_html=True)
        st.markdown('<h5>⚡ Recommended Actions</h5>', unsafe_allow_html=True)

        if entity_id and has_sender:
            is_s = filtered_df["Sender_account"].astype(str) == entity_id
            e_fraud_c = int(filtered_df.loc[is_s, "Is_laundering"].sum()) if has_fraud else 0
            if e_fraud_c > 0:
                actions = [
                    ("🚨", "File SAR Report", "Urgent", "urgent"),
                    ("🔒", "Freeze Account", "High", "urgent"),
                    ("🔍", "Trace Full Network", "Rec", "rec"),
                    ("📊", "Export Evidence Package", "", "info"),
                ]
            else:
                actions = [
                    ("📋", "Review Transaction History", "Rec", "rec"),
                    ("🔍", "Expand Entity Network", "", "info"),
                    ("✅", "Clear — Mark Reviewed", "", "info"),
                ]
        else:
            actions = [
                ("🔍", "Select an Entity Above", "", "info"),
                ("📊", "Export Dataset Analysis", "", "info"),
                ("🧪", "Train Model on Dataset", "", "info"),
            ]

        for icon, text, badge, bcls in actions:
            badge_html = f'<span class="ra-action-priority {bcls}">{badge}</span>' if badge else ""
            st.markdown(
                f'<div class="ra-action-card">'
                f'<span class="ra-action-icon">{icon}</span>'
                f'<span class="ra-action-text">{text}</span>'
                f'{badge_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 6. AI Risk Briefing ──────────────────────
    st.markdown("")
    st.markdown(
        '<div class="ra-llm-panel">'
        '<h5>🤖 AI Risk Briefing</h5>',
        unsafe_allow_html=True,
    )
    with st.spinner("Generating insight…"):
        insight = _ra_get_llm_dataset_insight(filtered_df, ds_record, rule_store)
    st.markdown(f'<div class="ra-llm-insight">{insight}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 7. Suggested Prompts ─────────────────────
    st.markdown("")
    st.markdown("**💡 Explore Further**")
    _prompts = [
        "Which accounts show structuring behavior?",
        "Summarize cross-border transaction anomalies",
        "Show top 10 highest-volume sender accounts",
        "Identify fan-out or fan-in laundering patterns",
        "Compare fraud rates by payment type",
        "Generate a compliance briefing for this dataset",
    ]
    prompt_cols = st.columns(3)
    for idx, ptxt in enumerate(_prompts):
        col = prompt_cols[idx % 3]
        with col:
            if st.button(f"↪ {ptxt}", key=f"ra_prompt_{idx}", use_container_width=True):
                st.session_state["_pending_prompt"] = ptxt
                st.info("💡 Prompt queued — switch to the **Data Query Assistant** sub-tab above to see the response.")



def section_intelligence_hub(orchestrator: RiskOrchestrator) -> None:
    """Intelligence Hub: Case Monitor + Batch Simulation."""
    section_case_intelligence(orchestrator)
    st.markdown("---")
    section_batch_simulation(orchestrator)


def section_model_studio() -> None:
    """Model Studio: Data Generator → Training → Explainability."""
    section_data_generator()
    st.markdown("---")
    section_training_control()
    st.markdown("---")
    section_explainability()


def main() -> None:
    render_page_style()
    orchestrator = get_orchestrator()
    rule_store = get_rule_store()

    # Sync session rules into nlp_service on every rerun
    set_session_rules(rule_store.get_rules())

    sidebar_status(orchestrator, rule_store)

    tabs = st.tabs(
        [
            "📂 Datasets",
            "🔍 Intelligence Hub",
            "🧪 Model Studio",
        ]
    )

    _tab_handlers = [
        ("Datasets", lambda: section_datasets_overview()),
        ("Intelligence Hub", lambda: section_intelligence_hub(orchestrator)),
        ("Model Studio", lambda: section_model_studio()),
    ]

    for tab, (name, handler) in zip(tabs, _tab_handlers):
        with tab:
            try:
                handler()
            except Exception as exc:
                st.error(f"Error in {name} tab: {exc}")


if __name__ == "__main__":
    main()
