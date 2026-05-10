from __future__ import annotations

import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - local fallback for minimal kernels
    BaseSettings = object
    SettingsConfigDict = dict


API_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    output_dir: str = os.getenv("OUTPUT_DIR", "../../output")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    if BaseSettings is not object:
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def output_path(self) -> Path:
        path = Path(self.output_dir)
        if path.is_absolute():
            return path
        return (API_ROOT / path).resolve()


settings = Settings()
