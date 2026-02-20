"""Tests for the dataset manager service."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.dataset_manager import (
    DatasetRecord,
    _compute_risk_level,
    _detect_label_column,
    _load_registry,
    _save_registry,
    delete_dataset,
    get_dataset,
    list_datasets,
    register_dataset,
    update_status,
    upload_and_register,
)
import app.services.dataset_manager as dm


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path, monkeypatch):
    """Point the dataset registry and dir to a temp folder for every test."""
    ds_dir = tmp_path / "datasets"
    ds_dir.mkdir()
    monkeypatch.setattr(dm, "DATASETS_DIR", ds_dir)
    monkeypatch.setattr(dm, "REGISTRY_PATH", ds_dir / "_registry.json")
    yield


def _make_csv(tmp_path: Path, name: str = "test.csv", rows: int = 50, fraud_ratio: float = 0.2) -> Path:
    """Helper: create a minimal CSV with a label column."""
    import csv

    p = tmp_path / name
    fraud_count = int(rows * fraud_ratio)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["account_id", "transaction_amount", "label"])
        for i in range(rows):
            w.writerow([f"acct_{i}", 1000 + i * 10, 1 if i < fraud_count else 0])
    return p


# ── DatasetRecord ────────────────────────────────────────────────────────────


class TestDatasetRecord:
    def test_fraud_pct(self):
        r = DatasetRecord(
            dataset_id="abc", name="test", file_path="/x.csv",
            upload_date="2026-01-01", fraud_ratio=0.123,
        )
        assert r.fraud_pct == "12.3%"

    def test_human_size_kb(self):
        r = DatasetRecord(
            dataset_id="abc", name="test", file_path="/x.csv",
            upload_date="2026-01-01", file_size_bytes=2048,
        )
        assert "KB" in r.human_size

    def test_human_size_mb(self):
        r = DatasetRecord(
            dataset_id="abc", name="test", file_path="/x.csv",
            upload_date="2026-01-01", file_size_bytes=5 * 1024 * 1024,
        )
        assert "MB" in r.human_size

    def test_to_dict_includes_computed(self):
        r = DatasetRecord(
            dataset_id="abc", name="test", file_path="/x.csv",
            upload_date="2026-01-01", fraud_ratio=0.5, file_size_bytes=1024,
        )
        d = r.to_dict()
        assert "fraud_pct" in d
        assert "human_size" in d


# ── Risk level heuristic ────────────────────────────────────────────────────


class TestComputeRiskLevel:
    def test_high(self):
        assert _compute_risk_level(0.35) == "High"

    def test_medium(self):
        assert _compute_risk_level(0.15) == "Medium"

    def test_low(self):
        assert _compute_risk_level(0.05) == "Low"

    def test_unknown(self):
        assert _compute_risk_level(0.0) == "Unknown"


# ── Label detection ─────────────────────────────────────────────────────────


class TestDetectLabelColumn:
    def test_label(self):
        assert _detect_label_column(["id", "amount", "label"]) == "label"

    def test_isFraud(self):
        assert _detect_label_column(["step", "amount", "isFraud"]) == "isFraud"

    def test_is_laundering(self):
        assert _detect_label_column(["Amount", "Is_laundering"]) == "Is_laundering"

    def test_case_insensitive(self):
        assert _detect_label_column(["LABEL", "amount"]) == "LABEL"

    def test_none(self):
        assert _detect_label_column(["id", "amount", "note"]) is None


# ── Register / list / get / delete ──────────────────────────────────────────


class TestRegisterDataset:
    def test_register_creates_record(self, tmp_path):
        csv = _make_csv(tmp_path, rows=100, fraud_ratio=0.3)
        record = register_dataset(csv, name="My Dataset", notes="test")
        assert record.name == "My Dataset"
        assert record.total_rows == 100
        assert record.fraud_count == 30
        assert record.risk_level == "High"
        assert record.notes == "test"
        assert len(record.dataset_id) == 12

    def test_list_returns_registered(self, tmp_path):
        csv = _make_csv(tmp_path, rows=20)
        register_dataset(csv)
        datasets = list_datasets()
        assert len(datasets) == 1
        assert datasets[0].total_rows == 20

    def test_get_by_id(self, tmp_path):
        csv = _make_csv(tmp_path, rows=20)
        rec = register_dataset(csv)
        found = get_dataset(rec.dataset_id)
        assert found is not None
        assert found.dataset_id == rec.dataset_id

    def test_get_missing(self):
        assert get_dataset("nonexistent") is None

    def test_delete(self, tmp_path):
        csv = _make_csv(tmp_path, rows=20)
        rec = register_dataset(csv)
        assert delete_dataset(rec.dataset_id) is True
        assert list_datasets() == []

    def test_delete_nonexistent(self):
        assert delete_dataset("nope") is False


class TestUpdateStatus:
    def test_update(self, tmp_path):
        csv = _make_csv(tmp_path, rows=10)
        rec = register_dataset(csv)
        assert update_status(rec.dataset_id, "Completed") is True
        updated = get_dataset(rec.dataset_id)
        assert updated is not None
        assert updated.status == "Completed"

    def test_update_nonexistent(self):
        assert update_status("nope", "Completed") is False


class TestUploadAndRegister:
    def test_upload(self, tmp_path):
        csv = _make_csv(tmp_path, name="upload.csv", rows=25, fraud_ratio=0.1)
        raw_bytes = csv.read_bytes()
        rec = upload_and_register(raw_bytes, "upload.csv", name="Uploaded DS")
        assert rec.name == "Uploaded DS"
        assert rec.total_rows == 25
        # File should be saved in datasets dir
        assert Path(rec.file_path).exists()

    def test_upload_collision(self, tmp_path):
        csv = _make_csv(tmp_path, name="dup.csv", rows=10)
        raw = csv.read_bytes()
        r1 = upload_and_register(raw, "dup.csv")
        r2 = upload_and_register(raw, "dup.csv")
        assert r1.file_path != r2.file_path
        assert len(list_datasets()) == 2


class TestMultipleDatasets:
    def test_ordering_newest_first(self, tmp_path):
        for i in range(3):
            csv = _make_csv(tmp_path, name=f"ds_{i}.csv", rows=10 + i)
            register_dataset(csv, name=f"Dataset {i}")
        datasets = list_datasets()
        assert len(datasets) == 3
        # newest (last registered) should be first
        assert datasets[0].name == "Dataset 2"


class TestRegistryPersistence:
    def test_save_and_load(self):
        records = [{"dataset_id": "abc", "name": "test"}]
        _save_registry(records)
        loaded = _load_registry()
        assert loaded == records

    def test_empty_on_missing(self):
        assert _load_registry() == []
