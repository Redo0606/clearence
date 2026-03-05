"""Embedding-based entity deduplication. Maps similar entity names to a canonical form."""

import logging
import threading

import numpy as np
from sentence_transformers import SentenceTransformer

from ontology_builder.constants import SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

# Load once; reuse across calls
_model: SentenceTransformer | None = None
_lock = threading.Lock()
entity_vectors: dict[str, np.ndarray] = {}


def _get_model() -> SentenceTransformer:
    """Return lazily-loaded SentenceTransformer (thread-safe)."""
    global _model
    with _lock:
        if _model is None:
            logger.debug("[Canonicalizer] Loading SentenceTransformer model")
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        return _model


def canonicalize(entity_name: str) -> str:
    """Return canonical form: existing similar entity or new (added to cache).

    Args:
        entity_name: Raw entity name from extraction.

    Returns:
        Canonical name (existing if similarity >= SIMILARITY_THRESHOLD, else input).
    """
    name = entity_name.strip()
    if not name:
        return name

    model = _get_model()
    emb = model.encode(name, convert_to_numpy=True, show_progress_bar=False)

    with _lock:
        # Check cache: if similar entity exists, return it; else add and return input
        for existing_name, vec in entity_vectors.items():
            sim = np.dot(emb, vec) / (np.linalg.norm(emb) * np.linalg.norm(vec) + 1e-9)
            if sim >= SIMILARITY_THRESHOLD:
                logger.debug("[Canonicalizer] %r -> %r (sim=%.3f)", name, existing_name, sim)
                return existing_name
        entity_vectors[name] = emb
        logger.debug("[Canonicalizer] New entity added to cache: %r | cache_size=%d", name, len(entity_vectors))
        return name


def seed_from_entities(entity_names: list[str]) -> None:
    """Pre-populate the canonicalizer cache with known entity names.

    Call when loading a KB so that enrichment matches against existing entities.
    Ensures consistent canonicalization across restarts.
    """
    if not entity_names:
        return
    model = _get_model()
    with _lock:
        for name in entity_names:
            n = (name or "").strip()
            if not n or n in entity_vectors:
                continue
            emb = model.encode(n, convert_to_numpy=True, show_progress_bar=False)
            entity_vectors[n] = emb
        logger.debug("[Canonicalizer] Seeded %d entities | cache_size=%d", len(entity_names), len(entity_vectors))
