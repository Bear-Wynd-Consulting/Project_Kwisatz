from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import FrozenSet


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Authentication
    API_KEYS: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    DEFAULT_MODEL: str = "gemma4:latest"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Rate limiting
    RATE_LIMIT_GLOBAL: str = "200/minute"
    RATE_LIMIT_PER_KEY: str = "60/minute"

    # Server
    GATEWAY_PORT: int = 8000
    UVICORN_WORKERS: int = 2
    LOG_LEVEL: str = "INFO"

    # Parsed fields (populated by validators)
    api_key_set: FrozenSet[str] = frozenset()
    allowed_origins_list: list[str] = []

    @model_validator(mode="after")
    def parse_compound_fields(self) -> "Settings":
        # Parse API keys — fail fast if none are configured
        keys = {k.strip() for k in self.API_KEYS.split(",") if k.strip()}
        if not keys:
            raise ValueError(
                "API_KEYS is empty. Set at least one key in .env "
                "(generate one with: bash scripts/generate-api-key.sh)"
            )
        self.api_key_set = frozenset(keys)

        # Parse allowed origins
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")
        self.allowed_origins_list = origins

        return self

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return v.upper()


# Module-level singleton — imported by all other modules
settings = Settings()
