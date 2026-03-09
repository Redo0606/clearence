"""Session and long-term agent memory for persistent knowledge across conversations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import orjson

from ontology_builder.agent.graph_reasoner import ReasoningGraph

logger = logging.getLogger(__name__)

_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
_AGENT_MEMORY_DIR = _STORAGE_DIR / "agent_memory"
_ONTOLOGY_EXPANSIONS_DIR = _STORAGE_DIR / "ontology_expansions"


def _ensure_dirs() -> None:
    _AGENT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _ONTOLOGY_EXPANSIONS_DIR.mkdir(parents=True, exist_ok=True)


class MemoryManager:
    """Manages session (in-memory) and long-term (disk) agent memory."""

    def __init__(self, kb_id: str | None = None):
        self.kb_id = kb_id or ""
        self._session_conversation: list[dict[str, Any]] = []
        self._session_reasoning_graph: ReasoningGraph | None = None

    def get_session_conversation(self) -> list[dict[str, Any]]:
        """Return current session conversation history."""
        return list(self._session_conversation)

    def add_to_session(self, query: str, answer: str, reasoning: str = "") -> None:
        """Append a Q&A turn to session memory."""
        self._session_conversation.append({
            "query": query,
            "answer": answer,
            "reasoning": reasoning,
        })

    def set_session_reasoning_graph(self, graph: ReasoningGraph | None) -> None:
        """Store the current reasoning graph for session context."""
        self._session_reasoning_graph = graph

    def get_session_reasoning_graph(self) -> ReasoningGraph | None:
        """Return the session reasoning graph if any."""
        return self._session_reasoning_graph

    def save_ontology_expansion(
        self,
        concepts: list[str],
        relations: list[dict[str, str]],
        source_query: str = "",
    ) -> None:
        """Persist discovered ontology expansions for future KB updates."""
        _ensure_dirs()
        if not self.kb_id:
            return

        path = _ONTOLOGY_EXPANSIONS_DIR / f"{self.kb_id}_expansions.jsonl"
        entry = {
            "concepts": concepts,
            "relations": relations,
            "source_query": source_query,
        }
        try:
            with path.open("ab") as f:
                f.write(orjson.dumps(entry) + b"\n")
            logger.debug("[MemoryManager] Saved ontology expansion to %s", path.name)
        except OSError as e:
            logger.warning("[MemoryManager] Failed to save expansion: %s", e)

    def load_long_term_memory(self) -> dict[str, Any]:
        """Load long-term memory for the current KB (discovered concepts, relations)."""
        _ensure_dirs()
        if not self.kb_id:
            return {}

        path = _AGENT_MEMORY_DIR / f"{self.kb_id}_memory.json"
        if not path.exists():
            return {}

        try:
            data = orjson.loads(path.read_bytes())
            return dict(data) if isinstance(data, dict) else {}
        except (OSError, orjson.JSONDecodeError) as e:
            logger.warning("[MemoryManager] Failed to load long-term memory: %s", e)
            return {}

    def save_long_term_memory(self, data: dict[str, Any]) -> None:
        """Persist long-term memory for the current KB."""
        _ensure_dirs()
        if not self.kb_id:
            return

        path = _AGENT_MEMORY_DIR / f"{self.kb_id}_memory.json"
        try:
            path.write_bytes(orjson.dumps(data))
            logger.debug("[MemoryManager] Saved long-term memory to %s", path.name)
        except OSError as e:
            logger.warning("[MemoryManager] Failed to save long-term memory: %s", e)

    def clear_session(self) -> None:
        """Clear session memory (conversation and reasoning graph)."""
        self._session_conversation = []
        self._session_reasoning_graph = None
