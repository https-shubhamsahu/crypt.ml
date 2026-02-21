from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DatasetOut(BaseModel):
    dataset_id: str
    name: str
    upload_date: str
    total_rows: int
    total_columns: int
    human_size: str
    risk_level: str
    status: str
    fraud_pct: str


class ValidationCheck(BaseModel):
    key: str
    title: str
    kind: str
    detail: str


class DatasetSummaryResponse(BaseModel):
    dataset_id: str
    date_range: str
    jurisdictions: int
    duplicate_count: int
    checks: List[ValidationCheck]


class TransactionOut(BaseModel):
    tx_id: str = Field(description="Synthetic transaction identifier")
    date: str
    entity: str
    amount: str
    risk: str


class DatasetTransactionsResponse(BaseModel):
    dataset_id: str
    items: List[TransactionOut]


class LabeledValue(BaseModel):
    label: str
    value: float


class LabeledCount(BaseModel):
    label: str
    count: int


class DatasetAnalyticsResponse(BaseModel):
    dataset_id: str
    total_processed: int
    active_alerts: int
    high_risk_entities: int
    risk_distribution: List[LabeledValue]
    alerts_over_time: List[LabeledCount]
    payment_type_distribution: List[LabeledCount]
    currency_distribution: List[LabeledCount]
    top_entities: List[LabeledCount]
