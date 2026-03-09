"""Persist reasoning steps to storage for explainability and reasoning viewer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import orjson

from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.agent.ontology_gap_detector import OntologyGap

logger = logging.getLogger(__name__)

_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
_REASONING_LOGS_DIR = _STORAGE_DIR / "reasoning_logs"


def _ensure_logs_dir() -> Path:
    _REASONING_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return _REASONING_LOGS_DIR


def log_reasoning(
    session_id: str,
    query: str,
    steps: list[dict[str, Any]],
    graph: ReasoningGraph,
    gaps: list[OntologyGap],
    answer: str = "",
    reasoning: str = "",
) -> Path | None:
    """Write reasoning log to storage/reasoning_logs/{session_id}.json.

    Args:
        session_id: Unique session identifier.
        query: Original user query.
        steps: List of {question, answer, concepts, relations} per exploration step.
        graph: Final reasoning graph.
        gaps: Detected ontology gaps.
        answer: Final synthesized answer.
        reasoning: Final reasoning text.

    Returns:
        Path to the written log file, or None on failure.
    """
    if not session_id:
        return None

    _ensure_logs_dir()
    path = _REASONING_LOGS_DIR / f"{session_id}.json"

    gaps_serializable = [
        {
            "gap_type": g.gap_type,
            "subject": g.subject,
            "relation": g.relation,
            "target": g.target,
            "description": g.description,
        }
        for g in gaps
    ]

    payload = {
        "query": query,
        "steps": steps,
        "graph": graph.to_dict(),
        "gaps": gaps_serializable,
        "answer": answer,
        "reasoning": reasoning,
    }

    try:
        path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        logger.debug("[ReasoningLogger] Wrote log to %s", path)
        return path
    except OSError as e:
        logger.warning("[ReasoningLogger] Failed to write log: %s", e)
        return None


def load_reasoning_log(session_id: str) -> dict[str, Any] | None:
    """Load a reasoning log by session ID."""
    if not session_id:
        return None

    path = _REASONING_LOGS_DIR / f"{session_id}.json"
    if not path.exists():
        return None

    try:
        return orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError) as e:
        logger.warning("[ReasoningLogger] Failed to load log: %s", e)
        return None


def get_reasoning_logs_dir() -> Path:
    """Return the reasoning logs directory path."""
    return _ensure_logs_dir()
