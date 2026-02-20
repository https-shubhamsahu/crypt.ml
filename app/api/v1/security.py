from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.sharing_config import SHARING_CONFIG

# This registers x-api-key in the OpenAPI spec so Swagger UI shows an Authorize button.
_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def require_api_key(
    x_api_key: str | None = Security(_api_key_header),
) -> None:
    """Enforce API key when AEGIS_REQUIRE_API_KEY=true."""
    if not SHARING_CONFIG.require_api_key:
        return

    if not SHARING_CONFIG.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key protection enabled but AEGIS_API_KEY is not configured.",
        )

    if x_api_key != SHARING_CONFIG.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing x-api-key header.",
        )
