"""Pydantic schemas for the synthetic data generation API."""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class GenerateDataRequest(BaseModel):
    num_rows: int = Field(default=1000, ge=20, le=500_000, description="Total rows to generate")
    fraud_ratio: float = Field(default=0.15, ge=0.01, le=0.95, description="Fraction of rows that are fraud/laundering")
    schema: str = Field(default="unified", description="One of: unified, paysim, aml_cft")
    seed: int = Field(default=42, description="Random seed for reproducibility")
    num_accounts: int = Field(default=200, ge=10, le=100_000, description="Distinct account IDs (PaySim/AML-CFT)")
    start_date: str = Field(default="2025-01-01", description="Start date for timestamps (AML-CFT)")
    days_span: int = Field(default=90, ge=1, le=3650, description="Date range in days (AML-CFT)")


class GenerateDataSaveResponse(BaseModel):
    status: str
    path: str
    rows: int
    fraud_count: int
    legit_count: int
    schema: str
    columns: List[str]


class SchemaInfoResponse(BaseModel):
    schemas: Dict[str, List[str]]
