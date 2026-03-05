"""Shared constants, paths, and helpers for ontology API."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # ontology_builder/ui/api -> repo root
_DOCUMENTS_RAW = _REPO_ROOT / "documents" / "raw"


def get_documents_raw() -> Path:
    """Return the raw documents upload directory."""
    return _DOCUMENTS_RAW


def get_allowed_suffixes() -> set[str]:
    """Return allowed file suffixes for upload."""
    return {".pdf", ".docx", ".txt", ".md"}


def get_active_pipelines() -> dict[str, threading.Event]:
    """Return the dict of active pipeline cancel events."""
    return _active_pipelines


_active_pipelines: dict[str, threading.Event] = {}


def sse_event(data: dict) -> str:
    """Format dict as SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def apply_env_overrides(
    model: str | None = None,
    workers: int | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    temperature: float | None = None,
) -> dict[str, str | None]:
    """Apply form overrides to environment for pipeline execution.

    Returns the previous env values for later restore. Clears settings cache.
    """
    old_env = {
        "ONTOLOGY_LLM_MODEL": os.environ.get("ONTOLOGY_LLM_MODEL"),
        "CHUNK_SIZE": os.environ.get("CHUNK_SIZE"),
        "CHUNK_OVERLAP": os.environ.get("CHUNK_OVERLAP"),
        "LLM_PARALLEL_WORKERS": os.environ.get("LLM_PARALLEL_WORKERS"),
        "LLM_TEMPERATURE": os.environ.get("LLM_TEMPERATURE"),
    }
    if model:
        os.environ["ONTOLOGY_LLM_MODEL"] = model
    if workers is not None:
        os.environ["LLM_PARALLEL_WORKERS"] = str(workers)
    if chunk_size is not None:
        os.environ["CHUNK_SIZE"] = str(chunk_size)
    if chunk_overlap is not None:
        os.environ["CHUNK_OVERLAP"] = str(chunk_overlap)
    if temperature is not None:
        os.environ["LLM_TEMPERATURE"] = str(temperature)
    get_settings.cache_clear()
    return old_env


def restore_env(old_env: dict[str, str | None]) -> None:
    """Restore environment from snapshot and clear settings cache."""
    for key, val in old_env.items():
        if val is not None:
            os.environ[key] = val
        elif key in os.environ:
            del os.environ[key]
    get_settings.cache_clear()


def build_report_dict(
    report_dict: dict[str, Any],
    ontology_name: str,
    totals: dict[str, Any] | None = None,
    document_display: str | None = None,
) -> dict[str, Any]:
    """Build pipeline_report dict for SSE complete event."""
    raw_totals = totals if totals is not None else report_dict.get("totals", {})
    totals_normalized = dict(raw_totals)
    if "relations" not in totals_normalized and "edges" in totals_normalized:
        totals_normalized["relations"] = totals_normalized["edges"]
    return {
        "document_path": document_display or report_dict.get("document_path", ""),
        "total_chunks": report_dict.get("total_chunks", 0),
        "totals": totals_normalized,
        "extraction_totals": report_dict.get("extraction_totals", {}),
        "llm_inferred_relations": report_dict.get("llm_inferred_relations", 0),
        "reasoning": report_dict.get("reasoning", {}),
        "elapsed_seconds": report_dict.get("elapsed_seconds", 0.0),
        "extraction_mode": report_dict.get("extraction_mode", ""),
        "chunk_stats": report_dict.get("chunk_stats", []),
        "ontology_name": ontology_name,
    }


def streaming_sse_headers() -> dict[str, str]:
    """SSE response headers for streaming endpoints."""
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
