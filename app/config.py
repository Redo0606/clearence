"""Pydantic settings for LLM (LM Studio/OpenAI), upload limits, and timeouts."""

import functools
import os
import re
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _in_docker() -> bool:
    """Return True if running inside a Docker container (checks /.dockerenv)."""
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
    # None = auto: 2 workers for local (LM Studio), 30 for ChatGPT/OpenAI cloud (max throughput for gpt-4o-mini). Override via LLM_PARALLEL_WORKERS.
    llm_parallel_workers: int | None = None
    # Max chars per chunk sent to LLM (avoids context overflow). 0 = no truncation.
    llm_max_chunk_chars: int = 600
    # Soft token budget for entire prompt (system + user). Prevents context overflow.
    llm_max_prompt_tokens: int = 3000
    # Chunk size and overlap for document splitting. Larger chunks = fewer API calls (faster with gpt-4o-mini).
    chunk_size: int = 1200
    chunk_overlap: int = 200
    # LLM sampling temperature (0.0–2.0). Lower = more deterministic.
    llm_temperature: float = 0.1
    # Max graph chars for relation inference; max classes/instances JSON for extractor stages. Larger for gpt-4o-mini.
    llm_max_graph_chars: int = 3000
    llm_max_taxonomy_chars: int = 2500
    llm_max_classes_json_chars: int = 1000
    llm_max_instances_json_chars: int = 800
    # Max context chars for QA answers.
    qa_max_context_chars: int = 4000
    # Force plain-text responses when no explicit response_format is provided.
    llm_force_text_mode: bool = True

    @model_validator(mode="after")
    def _apply_gpt4o_mini_defaults(self) -> "Settings":
        """Use larger chunk/context defaults when gpt-4o-mini (128k context).

        Only applies when env vars are unset; allows override via .env.
        """
        model_lower = (self.ontology_llm_model or "").lower()
        if "gpt-4o-mini" not in model_lower and "gpt-4.1o-mini" not in model_lower:
            return self
        updates: dict = {}
        if os.environ.get("CHUNK_SIZE") is None and self.chunk_size == 1200:
            updates["chunk_size"] = 10000
        if os.environ.get("CHUNK_OVERLAP") is None and self.chunk_overlap == 200:
            updates["chunk_overlap"] = 2000
        if os.environ.get("LLM_MAX_CHUNK_CHARS") is None and self.llm_max_chunk_chars == 600:
            updates["llm_max_chunk_chars"] = 4000
        if os.environ.get("LLM_MAX_PROMPT_TOKENS") is None and self.llm_max_prompt_tokens == 3000:
            updates["llm_max_prompt_tokens"] = 16000
        if os.environ.get("LLM_MAX_GRAPH_CHARS") is None and self.llm_max_graph_chars == 3000:
            updates["llm_max_graph_chars"] = 12000
        if os.environ.get("LLM_MAX_TAXONOMY_CHARS") is None and self.llm_max_taxonomy_chars == 2500:
            updates["llm_max_taxonomy_chars"] = 10000
        if os.environ.get("LLM_MAX_CLASSES_JSON_CHARS") is None and self.llm_max_classes_json_chars == 1000:
            updates["llm_max_classes_json_chars"] = 4000
        if os.environ.get("LLM_MAX_INSTANCES_JSON_CHARS") is None and self.llm_max_instances_json_chars == 800:
            updates["llm_max_instances_json_chars"] = 3200
        if os.environ.get("QA_MAX_CONTEXT_CHARS") is None and self.qa_max_context_chars == 4000:
            updates["qa_max_context_chars"] = 16000
        for k, v in updates.items():
            object.__setattr__(self, k, v)
        return self

    def is_llm_local(self) -> bool:
        """True if using local LM Studio (localhost, 127.0.0.1, host.docker.internal)."""
        base = (self.openai_base_url or "").lower()
        return any(h in base for h in ("localhost", "127.0.0.1", "host.docker.internal"))

    def get_llm_api_key(self) -> str:
        """Return API key for LLM. Uses placeholder for local LM Studio when key is empty."""
        if self.openai_api_key:
            return self.openai_api_key
        if self.is_llm_local():
            return "lm-studio"
        return ""

    def get_llm_parallel_workers(self) -> int:
        """Return parallel workers: 2 for local model, 30 for ChatGPT/OpenAI (max throughput for gpt-4o-mini). Override via LLM_PARALLEL_WORKERS."""
        if self.llm_parallel_workers is not None and self.llm_parallel_workers > 0:
            return self.llm_parallel_workers
        return 2 if self.is_llm_local() else 30


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (loaded from .env)."""
    return Settings()
