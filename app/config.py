"""Pydantic settings for LLM (LM Studio/OpenAI), upload limits, and timeouts."""

import functools
import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _in_docker() -> bool:
    """True if running inside a Docker container."""
    return Path("/.dockerenv").exists()


# LM Studio exposes an OpenAI-compatible API at http://localhost:1234/v1 by default.
# Set OPENAI_BASE_URL to use it; leave OPENAI_API_KEY empty (or any placeholder).
# For OpenAI cloud, set OPENAI_BASE_URL=https://api.openai.com/v1 and OPENAI_API_KEY=sk-...
class Settings(BaseSettings):
    """Application settings from env. Supports LM Studio (local) and OpenAI cloud."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    ontology_llm_model: str = "phi-3-mini-4k-instruct"
    log_level: str = "INFO"
    # Default: LM Studio local server. Override with OPENAI_BASE_URL for OpenAI cloud.
    openai_base_url: str = "http://localhost:1234/v1"

    @field_validator("openai_base_url", mode="after")
    @classmethod
    def _rewrite_localhost_for_docker(cls, v: str) -> str:
        """Inside Docker, localhost/127.0.0.1 cannot reach host LM Studio; use host.docker.internal."""
        if not _in_docker():
            return v
        return re.sub(r"(?i)(localhost|127\.0\.0\.1)", "host.docker.internal", v)
    upload_max_size_mb: int = 20
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3
    llm_parallel_workers: int = 2
    # Max chars per chunk sent to LLM (avoids context overflow). 0 = no truncation.
    llm_max_chunk_chars: int = 600
    # Soft token budget for entire prompt (system + user). Prevents context overflow.
    llm_max_prompt_tokens: int = 3000
    # Force plain-text responses when no explicit response_format is provided.
    # Structured calls that pass response_format (e.g. json_schema) take priority.
    llm_force_text_mode: bool = True

    def get_llm_api_key(self) -> str:
        """Return API key for LLM. Uses placeholder for local LM Studio when key is empty."""
        if self.openai_api_key:
            return self.openai_api_key
        if any(
            h in (self.openai_base_url or "").lower()
            for h in ("localhost", "127.0.0.1", "host.docker.internal")
        ):
            return "lm-studio"
        return ""


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (loaded from .env)."""
    return Settings()
