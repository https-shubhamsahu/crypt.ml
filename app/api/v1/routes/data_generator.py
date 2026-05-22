"""
API routes for synthetic training data generation.

Endpoints:
  POST /api/v1/generate-data       → generate and return CSV as download
  POST /api/v1/generate-data/save  → generate, save to data/, return metadata
  GET  /api/v1/generate-data/schemas → list supported schemas and their columns
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.v1.security import require_api_key
from app.schemas.data_generator import (
    GenerateDataRequest,
    GenerateDataSaveResponse,
    SchemaInfoResponse,
)
from app.services.data_generator import (
    SUPPORTED_SCHEMAS,
    GeneratorConfig,
    generate_and_save,
    generate_data,
    generate_to_csv_string,
    get_schema_preview,
)

router = APIRouter(prefix="/api/v1", tags=["data-generator"])

DEFAULT_OUTPUT = Path(__file__).resolve().parents[4] / "data" / "training_transactions.csv"


@router.get("/generate-data/schemas", response_model=SchemaInfoResponse)
def list_schemas() -> SchemaInfoResponse:
    """Return available data schemas and their column definitions."""
    schemas = {
        schema: get_schema_preview(schema) for schema in SUPPORTED_SCHEMAS
    }
    return SchemaInfoResponse(schemas=schemas)


@router.post("/generate-data")
def generate_csv(
    payload: GenerateDataRequest,
    _: None = Depends(require_api_key),
) -> Response:
    """Generate synthetic training data and return as a downloadable CSV."""
    config = GeneratorConfig(
        num_rows=payload.num_rows,
        fraud_ratio=payload.fraud_ratio,
        schema=payload.schema,
        seed=payload.seed,
        num_accounts=payload.num_accounts,
        start_date=payload.start_date,
        days_span=payload.days_span,
    )
    csv_content = generate_to_csv_string(config)
    filename = f"crypt_ml_synthetic_{config.schema}_{config.num_rows}rows.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-data/save", response_model=GenerateDataSaveResponse)
def generate_and_save_csv(
    payload: GenerateDataRequest,
    _: None = Depends(require_api_key),
) -> GenerateDataSaveResponse:
    """Generate synthetic data and save to disk for immediate training use."""
    config = GeneratorConfig(
        num_rows=payload.num_rows,
        fraud_ratio=payload.fraud_ratio,
        schema=payload.schema,
        seed=payload.seed,
        num_accounts=payload.num_accounts,
        start_date=payload.start_date,
        days_span=payload.days_span,
    )
    df = generate_data(config)
    output_path = DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    fraud_count = int(df["label"].sum()) if "label" in df.columns else int(
        df.get("isFraud", df.get("Is_laundering", 0)).sum()
    )

    return GenerateDataSaveResponse(
        status="saved",
        path=str(output_path),
        rows=len(df),
        fraud_count=fraud_count,
        legit_count=len(df) - fraud_count,
        schema=config.schema,
        columns=list(df.columns),
    )
