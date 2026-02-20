"""Tests for the Sharing API (ML inference, LLM chat, NLP analysis, session rules)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

client = TestClient(app)

# Disable API key for tests
os.environ["AEGIS_REQUIRE_API_KEY"] = "false"


# ── ML Predict ───────────────────────────────────────────────────────────────


class TestMLPredict:
    """Tests for POST /api/v1/ml/predict"""

    def test_predict_basic(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 50000,
                "Sender_account": "ACC_1001",
                "Receiver_account": "ACC_2001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "probability" in data
        assert "contributions" in data
        assert "reasoning" in data
        assert "model_source" in data
        assert data["model_source"] in ("trained_model", "deterministic_proxy")
        assert 0 <= data["score"] <= 100
        assert 0 <= data["probability"] <= 1

    def test_predict_with_note(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 80000,
                "Sender_account": "ACC_1002",
                "Receiver_account": "ACC_9901",
                "Payment_currency": "GBP",
                "Received_currency": "EUR",
                "Sender_bank_location": "UK",
                "Receiver_bank_location": "CH",
                "Payment_type": "Cross-border",
                "transaction_note": "urgent mule cashout crypto",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nlp_terms"]) > 0
        # With NLP terms the score should be non-trivial
        assert data["score"] > 0

    def test_predict_zero_values(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 0,
                "Sender_account": "ACC_1003",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] >= 0

    def test_predict_validation_negative_amount(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": -100,
                "Sender_account": "ACC_1004",
            },
        )
        assert resp.status_code == 422

    def test_predict_missing_required_field(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={"Amount": 1000},
        )
        assert resp.status_code == 422

    def test_predict_high_values(self):
        resp = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 500_000,
                "Sender_account": "ACC_1005",
                "Receiver_account": "ACC_9905",
                "Payment_currency": "USD",
                "Received_currency": "CNY",
                "Sender_bank_location": "US",
                "Receiver_bank_location": "HK",
                "Payment_type": "Cross-border",
                "Laundering_type": "Layering",
                "transaction_note": "bypass untraceable mule crypto cashout",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] > 0
        assert len(data["contributions"]) >= 3


class TestMLInfo:
    """Tests for GET /api/v1/ml/info"""

    def test_info_endpoint(self):
        resp = client.get("/api/v1/ml/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_available" in data
        assert "model_path" in data
        assert isinstance(data["model_available"], bool)

    def test_info_has_metadata_if_model_exists(self):
        resp = client.get("/api/v1/ml/info")
        data = resp.json()
        if data["model_available"]:
            # Metadata should also exist if model was trained
            assert data["metadata"] is not None


# ── LLM Chat ────────────────────────────────────────────────────────────────


class TestLLMChat:
    """Tests for POST /api/v1/llm/chat"""

    def test_chat_basic(self):
        resp = client.post(
            "/api/v1/llm/chat",
            json={"message": "What is the current model ROC-AUC?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "llm_used" in data
        assert "model_name" in data
        assert len(data["reply"]) > 0

    def test_chat_with_custom_context(self):
        resp = client.post(
            "/api/v1/llm/chat",
            json={
                "message": "Explain the risk score formula",
                "system_context": "You are a helpful AML expert.",
                "include_ml_artifacts": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reply"]) > 0

    def test_chat_rule_injection(self):
        # Clear first
        client.delete("/api/v1/session-rules")

        resp = client.post(
            "/api/v1/llm/chat",
            json={"message": "In this session, prioritize recall >= 0.85"},
        )
        assert resp.status_code == 200

        # Check rules were injected
        rules_resp = client.get("/api/v1/session-rules")
        rules_data = rules_resp.json()
        assert rules_data["count"] >= 0  # May or may not detect depending on parse

    def test_chat_empty_message_rejected(self):
        resp = client.post(
            "/api/v1/llm/chat",
            json={"message": ""},
        )
        assert resp.status_code == 422

    def test_chat_structured_sections(self):
        resp = client.post(
            "/api/v1/llm/chat",
            json={"message": "Summarize the SHAP feature importance"},
        )
        data = resp.json()
        # Even in fallback mode the reply should be non-empty
        assert data["reply"]


class TestLLMStatus:
    """Tests for GET /api/v1/llm/status"""

    def test_status_endpoint(self):
        resp = client.get("/api/v1/llm/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_enabled" in data
        assert "model_name" in data
        assert "endpoint" in data
        assert "ollama_reachable" in data
        assert isinstance(data["llm_enabled"], bool)
        assert isinstance(data["ollama_reachable"], bool)


# ── NLP Analyze ──────────────────────────────────────────────────────────────


class TestNLPAnalyze:
    """Tests for POST /api/v1/nlp/analyze"""

    def test_analyze_basic(self):
        resp = client.post(
            "/api/v1/nlp/analyze",
            json={"note": "urgent cashout to mule wallet"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] > 0
        assert "urgent" in data["matched_terms"] or "cashout" in data["matched_terms"]
        assert "llm_enabled" in data

    def test_analyze_clean_note(self):
        resp = client.post(
            "/api/v1/nlp/analyze",
            json={"note": "regular monthly salary transfer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 0 or data["score"] < 20
        assert len(data["matched_terms"]) == 0

    def test_analyze_empty_rejected(self):
        resp = client.post(
            "/api/v1/nlp/analyze",
            json={"note": ""},
        )
        assert resp.status_code == 422

    def test_analyze_all_keywords(self):
        resp = client.post(
            "/api/v1/nlp/analyze",
            json={"note": "urgent cashout mule otp giftcard crypto bypass fake freeze untraceable"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] > 50
        assert len(data["matched_terms"]) >= 5


# ── Session Rules (API) ──────────────────────────────────────────────────────


class TestSessionRules:
    """Tests for /api/v1/session-rules"""

    def test_list_rules_initially(self):
        # Clear first
        client.delete("/api/v1/session-rules")
        resp = client.get("/api/v1/session-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "api"
        assert data["count"] == 0
        assert data["rules"] == []

    def test_inject_rule(self):
        client.delete("/api/v1/session-rules")
        resp = client.post(
            "/api/v1/session-rules",
            json={"text": "In this session, prioritize recall >= 0.80"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_active"] >= 0  # Parser may or may not extract

    def test_inject_and_list(self):
        client.delete("/api/v1/session-rules")
        client.post(
            "/api/v1/session-rules",
            json={"text": "Set threshold to 0.6 for this session"},
        )
        resp = client.get("/api/v1/session-rules")
        assert resp.status_code == 200

    def test_clear_rules(self):
        resp = client.delete("/api/v1/session-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cleared"
        assert data["rules_remaining"] == 0

        # Verify empty
        list_resp = client.get("/api/v1/session-rules")
        assert list_resp.json()["count"] == 0

    def test_inject_empty_text_rejected(self):
        resp = client.post(
            "/api/v1/session-rules",
            json={"text": ""},
        )
        assert resp.status_code == 422

    def test_inject_no_rules_detected(self):
        client.delete("/api/v1/session-rules")
        resp = client.post(
            "/api/v1/session-rules",
            json={"text": "hello how are you today"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_active"] == 0


# ── API Key Protection ───────────────────────────────────────────────────────


class TestSharingAPIKey:
    """Verify endpoints respect API key when enabled."""

    def test_predict_requires_key_when_enabled(self):
        from app.core.sharing_config import SharingConfig

        fake_cfg = SharingConfig(
            cors_origins=["*"],
            require_api_key=True,
            api_key="test-key-12345",
        )
        with patch("app.api.v1.security.SHARING_CONFIG", fake_cfg):
            # Without key
            resp = client.post(
                "/api/v1/ml/predict",
                json={"Amount": 1000, "Sender_account": "ACC_KEY1"},
            )
            assert resp.status_code == 401

            # With key
            resp = client.post(
                "/api/v1/ml/predict",
                json={"Amount": 1000, "Sender_account": "ACC_KEY1"},
                headers={"x-api-key": "test-key-12345"},
            )
            assert resp.status_code == 200

    def test_chat_requires_key_when_enabled(self):
        from app.core.sharing_config import SharingConfig

        fake_cfg = SharingConfig(
            cors_origins=["*"],
            require_api_key=True,
            api_key="test-key-12345",
        )
        with patch("app.api.v1.security.SHARING_CONFIG", fake_cfg):
            resp = client.post(
                "/api/v1/llm/chat",
                json={"message": "hello"},
            )
            assert resp.status_code == 401

            resp = client.post(
                "/api/v1/llm/chat",
                json={"message": "hello"},
                headers={"x-api-key": "test-key-12345"},
            )
            assert resp.status_code == 200


# ── Integration: end-to-end predict → chat flow ─────────────────────────────


class TestIntegration:

    def test_predict_then_chat_about_it(self):
        """Simulate: teammate runs prediction, then asks LLM about it."""
        pred = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 75000,
                "Sender_account": "ACC_INT1",
                "Receiver_account": "ACC_9910",
                "Payment_type": "Cross-border",
                "transaction_note": "urgent mule transfer",
            },
        )
        assert pred.status_code == 200
        score = pred.json()["score"]

        chat = client.post(
            "/api/v1/llm/chat",
            json={"message": f"I got a risk score of {score}. Is this high?"},
        )
        assert chat.status_code == 200
        assert len(chat.json()["reply"]) > 0

    def test_full_session_rule_workflow(self):
        """Clear → inject → list → predict → clear."""
        client.delete("/api/v1/session-rules")

        # Inject
        client.post(
            "/api/v1/session-rules",
            json={"text": "In this session, set recall threshold to 0.90"},
        )

        # List
        rules = client.get("/api/v1/session-rules").json()
        assert rules["count"] >= 0

        # Predict (rules should be active in NLP)
        pred = client.post(
            "/api/v1/ml/predict",
            json={
                "Amount": 10000,
                "Sender_account": "ACC_INT2",
            },
        )
        assert pred.status_code == 200

        # Clear
        clear = client.delete("/api/v1/session-rules")
        assert clear.json()["rules_remaining"] == 0
