"""
Tests for the Synthetic Training Data Generator.

Covers:
  1. GeneratorConfig validation
  2. Unified schema generation
  3. PaySim schema generation
  4. AML-CFT schema generation
  5. Fraud ratio accuracy
  6. Seed reproducibility
  7. CSV string export
  8. Schema preview columns
  9. Training pipeline compatibility (to_model_schema round-trip)
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from app.services.data_generator import (
    SCHEMA_AML_CFT,
    SCHEMA_PAYSIM,
    SCHEMA_UNIFIED,
    SUPPORTED_SCHEMAS,
    GeneratorConfig,
    generate_data,
    generate_to_csv_string,
    get_schema_preview,
)


# ── 1) GeneratorConfig ──────────────────────────────────────────────────────

class TestGeneratorConfig:

    def test_defaults(self) -> None:
        config = GeneratorConfig()
        assert config.num_rows == 1000
        assert config.fraud_ratio == 0.15
        assert config.schema == SCHEMA_AML_CFT

    def test_min_rows_clamp(self) -> None:
        config = GeneratorConfig(num_rows=5)
        assert config.num_rows == 20  # clamped to min

    def test_fraud_ratio_clamp_high(self) -> None:
        config = GeneratorConfig(fraud_ratio=0.99)
        assert config.fraud_ratio == 0.95

    def test_fraud_ratio_clamp_low(self) -> None:
        config = GeneratorConfig(fraud_ratio=0.001)
        assert config.fraud_ratio == 0.01

    def test_invalid_schema(self) -> None:
        with pytest.raises(ValueError, match="schema must be one of"):
            GeneratorConfig(schema="invalid_schema")

    def test_all_schemas_valid(self) -> None:
        for schema in SUPPORTED_SCHEMAS:
            config = GeneratorConfig(schema=schema)
            assert config.schema == schema


# ── 2) Unified Schema Generation ────────────────────────────────────────────

class TestUnifiedGeneration:

    def test_basic_generation(self) -> None:
        config = GeneratorConfig(num_rows=100, schema=SCHEMA_UNIFIED)
        df = generate_data(config)
        assert len(df) == 100
        assert set(df.columns) == {
            "transaction_amount", "tx_count_last_hour", "has_upi",
            "nlp_signal", "label", "transaction_note",
        }

    def test_label_values(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=200, schema=SCHEMA_UNIFIED))
        assert set(df["label"].unique()) == {0, 1}

    def test_has_upi_binary(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=200, schema=SCHEMA_UNIFIED))
        assert set(df["has_upi"].unique()).issubset({0, 1})

    def test_transaction_amounts_positive(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_UNIFIED))
        assert (df["transaction_amount"] > 0).all()

    def test_nlp_signal_range(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=500, schema=SCHEMA_UNIFIED))
        assert (df["nlp_signal"] >= 0).all()
        assert (df["nlp_signal"] <= 100).all()


# ── 3) PaySim Schema Generation ─────────────────────────────────────────────

class TestPaySimGeneration:

    def test_basic_generation(self) -> None:
        config = GeneratorConfig(num_rows=100, schema=SCHEMA_PAYSIM)
        df = generate_data(config)
        assert len(df) == 100
        required_cols = {"step", "type", "amount", "nameOrig", "oldbalanceOrg",
                         "newbalanceOrig", "nameDest", "oldbalanceDest",
                         "newbalanceDest", "isFraud", "isFlaggedFraud", "transaction_note"}
        assert required_cols.issubset(set(df.columns))

    def test_fraud_labels(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=200, schema=SCHEMA_PAYSIM, fraud_ratio=0.3))
        assert set(df["isFraud"].unique()) == {0, 1}

    def test_step_range(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_PAYSIM))
        assert (df["step"] >= 1).all()
        assert (df["step"] <= 744).all()

    def test_amounts_positive(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_PAYSIM))
        assert (df["amount"] > 0).all()


# ── 4) AML-CFT Schema Generation ────────────────────────────────────────────

class TestAmlCftGeneration:

    def test_basic_generation(self) -> None:
        config = GeneratorConfig(num_rows=100, schema=SCHEMA_AML_CFT)
        df = generate_data(config)
        assert len(df) == 100
        required_cols = {"Time", "Date", "Sender_account", "Receiver_account",
                         "Amount", "Payment_currency", "Received_currency",
                         "Sender_bank_location", "Receiver_bank_location",
                         "Payment_type", "Is_laundering", "Laundering_type"}
        assert required_cols.issubset(set(df.columns))

    def test_date_format(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=50, schema=SCHEMA_AML_CFT))
        # All dates should parse
        pd.to_datetime(df["Date"])

    def test_time_format(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=50, schema=SCHEMA_AML_CFT))
        pd.to_datetime(df["Time"], format="%H:%M:%S")

    def test_laundering_labels(self) -> None:
        df = generate_data(GeneratorConfig(num_rows=200, schema=SCHEMA_AML_CFT, fraud_ratio=0.3))
        assert set(df["Is_laundering"].unique()) == {0, 1}


# ── 5) Fraud Ratio Accuracy ─────────────────────────────────────────────────

class TestFraudRatio:

    @pytest.mark.parametrize("schema", SUPPORTED_SCHEMAS)
    def test_ratio_close_to_target(self, schema: str) -> None:
        target = 0.20
        config = GeneratorConfig(num_rows=1000, fraud_ratio=target, schema=schema)
        df = generate_data(config)
        fraud_col = {"unified": "label", "paysim": "isFraud", "aml_cft": "Is_laundering"}[schema]
        actual_ratio = df[fraud_col].mean()
        assert abs(actual_ratio - target) < 0.02, f"Expected ~{target}, got {actual_ratio}"


# ── 6) Seed Reproducibility ─────────────────────────────────────────────────

class TestSeedReproducibility:

    @pytest.mark.parametrize("schema", SUPPORTED_SCHEMAS)
    def test_same_seed_same_output(self, schema: str) -> None:
        config = GeneratorConfig(num_rows=100, schema=schema, seed=123)
        df1 = generate_data(config)
        df2 = generate_data(config)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seed_different_output(self) -> None:
        df1 = generate_data(GeneratorConfig(num_rows=100, seed=1))
        df2 = generate_data(GeneratorConfig(num_rows=100, seed=2))
        assert not df1.equals(df2)


# ── 7) CSV String Export ─────────────────────────────────────────────────────

class TestCsvStringExport:

    def test_csv_string_parseable(self) -> None:
        config = GeneratorConfig(num_rows=50, schema=SCHEMA_UNIFIED)
        csv_str = generate_to_csv_string(config)
        assert isinstance(csv_str, str)
        assert csv_str.startswith("transaction_amount,")  # first column header
        # Round-trip: parse CSV string back
        from io import StringIO
        df = pd.read_csv(StringIO(csv_str))
        assert len(df) == 50

    @pytest.mark.parametrize("schema", SUPPORTED_SCHEMAS)
    def test_csv_round_trip(self, schema: str) -> None:
        csv_str = generate_to_csv_string(GeneratorConfig(num_rows=30, schema=schema))
        from io import StringIO
        df = pd.read_csv(StringIO(csv_str))
        assert len(df) == 30


# ── 8) Schema Preview ───────────────────────────────────────────────────────

class TestSchemaPreview:

    @pytest.mark.parametrize("schema", SUPPORTED_SCHEMAS)
    def test_preview_columns_non_empty(self, schema: str) -> None:
        columns = get_schema_preview(schema)
        assert len(columns) >= 5

    def test_unknown_schema_empty(self) -> None:
        assert get_schema_preview("unknown") == []

    def test_unified_columns_match_model_features(self) -> None:
        cols = get_schema_preview(SCHEMA_UNIFIED)
        assert "transaction_amount" in cols
        assert "label" in cols


# ── 9) Training Pipeline Compatibility ───────────────────────────────────────

class TestTrainingCompatibility:

    def test_unified_to_model_schema(self) -> None:
        """Unified data should pass through to_model_schema unchanged."""
        from scripts.train_ml import to_model_schema
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_UNIFIED))
        result = to_model_schema(df)
        assert len(result) == 100
        assert "label" in result.columns

    def test_paysim_to_model_schema(self) -> None:
        """PaySim data should transform to model schema."""
        from scripts.train_ml import to_model_schema
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_PAYSIM))
        result = to_model_schema(df)
        assert len(result) > 0
        assert "label" in result.columns
        assert "transaction_amount" in result.columns

    def test_aml_cft_to_model_schema(self) -> None:
        """AML-CFT data should transform to model schema."""
        from scripts.train_ml import to_model_schema
        df = generate_data(GeneratorConfig(num_rows=100, schema=SCHEMA_AML_CFT))
        result = to_model_schema(df)
        assert len(result) > 0
        assert "label" in result.columns
