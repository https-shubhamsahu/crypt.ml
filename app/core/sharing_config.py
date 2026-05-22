from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_cors_origins(raw_value: str | None) -> list[str]:
    if not raw_value:
        return ["*"]
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


@dataclass(frozen=True)
class SharingConfig:
    cors_origins: list[str]
    require_api_key: bool
    api_key: str

    @property
    def is_cors_wildcard(self) -> bool:
        return len(self.cors_origins) == 1 and self.cors_origins[0] == "*"


SHARING_CONFIG = SharingConfig(
    cors_origins=_parse_cors_origins(os.getenv("crypt.ml_CORS_ORIGINS", "*")),
    require_api_key=_as_bool(os.getenv("CRYPT_ML_REQUIRE_API_KEY"), default=False),
    api_key=os.getenv("crypt.ml_API_KEY", ""),
)
