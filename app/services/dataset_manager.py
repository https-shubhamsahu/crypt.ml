"""Dataset catalogue manager for crypt.ml.

Handles registration, metadata tracking, quick-stats computation, and
persistence of dataset records to a lightweight JSON registry.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "data" / "datasets"
REGISTRY_PATH = DATASETS_DIR / "_registry.json"

# ---------------------------------------------------------------------------
# Expected upload schema (AML-CFT)
# ---------------------------------------------------------------------------

UPLOAD_SCHEMA_COLUMNS = [
    "Time",
    "Date",
    "Sender_account",
    "Receiver_account",
    "Amount",
    "Payment_currency",
    "Received_currency",
    "Sender_bank_location",
    "Receiver_bank_location",
    "Payment_type",
    "Is_laundering",
    "Laundering_type",
]

UPLOAD_SCHEMA_REQUIRED = {c.lower() for c in UPLOAD_SCHEMA_COLUMNS}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

RiskLevel = Literal["Low", "Medium", "High", "Unknown"]
AnalysisStatus = Literal["Pending", "In Progress", "Completed"]


@dataclass
class DatasetRecord:
    """Metadata for a single uploaded dataset."""

    dataset_id: str
    name: str
    file_path: str
    upload_date: str  # ISO-8601
    total_rows: int = 0
    total_columns: int = 0
    fraud_count: int = 0
    legit_count: int = 0
    fraud_ratio: float = 0.0
    risk_level: RiskLevel = "Unknown"
    status: AnalysisStatus = "Pending"
    file_size_bytes: int = 0
    sha256: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    # Computed helpers -------------------------------------------------------
    @property
    def fraud_pct(self) -> str:
        return f"{self.fraud_ratio * 100:.1f}%"

    @property
    def human_size(self) -> str:
        size = self.file_size_bytes
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["fraud_pct"] = self.fraud_pct
        d["human_size"] = self.human_size
        return d


# ---------------------------------------------------------------------------
# Registry persistence
# ---------------------------------------------------------------------------


def _ensure_dir() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> List[Dict]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_registry(records: List[Dict]) -> None:
    _ensure_dir()
    REGISTRY_PATH.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_datasets() -> List[DatasetRecord]:
    """Return all registered datasets, newest first."""
    raw = _load_registry()
    datasets: List[DatasetRecord] = []
    for entry in raw:
        try:
            # Drop computed fields that aren't constructor args
            entry.pop("fraud_pct", None)
            entry.pop("human_size", None)
            datasets.append(DatasetRecord(**entry))
        except TypeError:
            continue
    datasets.sort(key=lambda d: d.upload_date, reverse=True)
    return datasets


def get_dataset(dataset_id: str) -> Optional[DatasetRecord]:
    for ds in list_datasets():
        if ds.dataset_id == dataset_id:
            return ds
    return None


def _detect_label_column(columns: List[str]) -> Optional[str]:
    """Find the fraud/label column — prioritise AML-CFT schema."""
    # AML-CFT schema first (primary upload format)
    candidates = ["Is_laundering", "is_laundering", "label", "isFraud", "is_fraud", "fraud"]
    for c in candidates:
        if c in columns:
            return c
    # Case-insensitive fallback
    lower_map = {col.lower(): col for col in columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def validate_upload_schema(columns: List[str]) -> List[str]:
    """Validate that the upload file matches the expected AML-CFT schema.

    Returns a list of missing columns (empty = valid).
    """
    present = {c.strip().lower() for c in columns}
    missing = [c for c in UPLOAD_SCHEMA_COLUMNS if c.lower() not in present]
    return missing


def _compute_risk_level(fraud_ratio: float) -> RiskLevel:
    if fraud_ratio >= 0.30:
        return "High"
    elif fraud_ratio >= 0.10:
        return "Medium"
    elif fraud_ratio > 0:
        return "Low"
    return "Unknown"


def _file_sha256(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def register_dataset(
    file_path: Path,
    name: Optional[str] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
    status: AnalysisStatus = "Pending",
) -> DatasetRecord:
    """Register a new dataset from a CSV/Excel file, compute quick stats."""
    import pandas as pd

    _ensure_dir()

    # Read file
    suffix = file_path.suffix.lower()
    if suffix in (".xls", ".xlsx"):
        df = pd.read_excel(file_path, nrows=None)
    else:
        df = pd.read_csv(file_path, nrows=None)

    total_rows = len(df)
    total_columns = len(df.columns)

    label_col = _detect_label_column(list(df.columns))
    if label_col is not None:
        fraud_count = int(df[label_col].sum())
    else:
        fraud_count = 0

    legit_count = total_rows - fraud_count
    fraud_ratio = fraud_count / total_rows if total_rows > 0 else 0.0

    record = DatasetRecord(
        dataset_id=uuid.uuid4().hex[:12],
        name=name or file_path.stem,
        file_path=str(file_path),
        upload_date=datetime.now(timezone.utc).isoformat(),
        total_rows=total_rows,
        total_columns=total_columns,
        fraud_count=fraud_count,
        legit_count=legit_count,
        fraud_ratio=round(fraud_ratio, 4),
        risk_level=_compute_risk_level(fraud_ratio),
        status=status,
        file_size_bytes=os.path.getsize(file_path),
        sha256=_file_sha256(file_path),
        notes=notes,
        tags=tags or [],
    )

    registry = _load_registry()
    registry.append(record.to_dict())
    _save_registry(registry)
    return record


def upload_and_register(
    uploaded_bytes: bytes,
    original_filename: str,
    name: Optional[str] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
) -> DatasetRecord:
    """Save uploaded bytes to datasets/ dir, then register."""
    _ensure_dir()
    safe_name = original_filename.replace(" ", "_")
    dest = DATASETS_DIR / safe_name

    # Avoid collisions
    counter = 1
    while dest.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        dest = DATASETS_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    dest.write_bytes(uploaded_bytes)
    return register_dataset(dest, name=name or dest.stem, notes=notes, tags=tags)


def update_status(dataset_id: str, status: AnalysisStatus) -> bool:
    """Update the analysis status of a dataset."""
    registry = _load_registry()
    for entry in registry:
        if entry.get("dataset_id") == dataset_id:
            entry["status"] = status
            _save_registry(registry)
            return True
    return False


def delete_dataset(dataset_id: str) -> bool:
    """Remove a dataset from the registry (optionally delete file)."""
    registry = _load_registry()
    updated = [e for e in registry if e.get("dataset_id") != dataset_id]
    if len(updated) == len(registry):
        return False
    _save_registry(updated)
    return True


def scan_existing_data_dir() -> int:
    """Auto-register any CSV/Excel files in data/ that aren't already tracked."""
    data_dir = PROJECT_ROOT / "data"
    known_paths = {ds.file_path for ds in list_datasets()}
    registered = 0

    for ext in ("*.csv", "*.xlsx", "*.xls"):
        for f in data_dir.glob(ext):
            # Skip internal files
            if f.name.startswith("_") or "session_rules" in str(f):
                continue
            if str(f) not in known_paths:
                try:
                    register_dataset(f)
                    registered += 1
                except Exception:
                    continue
    return registered


def _recompute_stats(dataset_id: str, file_path: Path) -> bool:
    """Re-read a dataset file and update registry stats (rows, fraud, hash, etc.)."""
    import pandas as pd

    suffix = file_path.suffix.lower()
    try:
        df = pd.read_excel(file_path) if suffix in (".xls", ".xlsx") else pd.read_csv(file_path)
    except Exception:
        return False

    label_col = _detect_label_column(list(df.columns))
    fraud_count = int(df[label_col].sum()) if label_col else 0
    total_rows = len(df)
    legit_count = total_rows - fraud_count
    fraud_ratio = fraud_count / total_rows if total_rows > 0 else 0.0

    registry = _load_registry()
    for entry in registry:
        if entry.get("dataset_id") == dataset_id:
            entry["total_rows"] = total_rows
            entry["total_columns"] = len(df.columns)
            entry["fraud_count"] = fraud_count
            entry["legit_count"] = legit_count
            entry["fraud_ratio"] = round(fraud_ratio, 4)
            entry["risk_level"] = _compute_risk_level(fraud_ratio)
            entry["file_size_bytes"] = os.path.getsize(file_path)
            entry["sha256"] = _file_sha256(file_path)
            # Update computed helpers
            entry.pop("fraud_pct", None)
            entry.pop("human_size", None)
            _save_registry(registry)
            return True
    return False
