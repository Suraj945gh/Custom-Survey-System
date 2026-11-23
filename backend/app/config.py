"""Settings, read from environment variables with safe defaults for local use."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'survey.db').as_posix()}")
    # Signs login tokens. MUST be changed outside local development.
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
    token_hours: int = int(os.getenv("TOKEN_HOURS", "12"))
    # Slow on purpose (makes guessing passwords expensive). Tests lower it to stay fast.
    password_iterations: int = int(os.getenv("PASSWORD_ITERATIONS", "200000"))
    default_deadline_days: int = int(os.getenv("DEFAULT_DEADLINE_DAYS", "15"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(512 * 1024)))
    cors_origins: list[str] = field(
        default_factory=lambda: _list(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    )


settings = Settings()
