"""Embedding-based entity deduplication. Maps similar entity names to a canonical form."""

import logging
import os
import re
import threading
from pathlib import Path

import numpy as np

from core.config import get_settings
from ontology_builder.constants import SIMILARITY_THRESHOLD
from ontology_builder.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# (normalized_key, kind) -> (canonical_display_name, embedding). kind = "class" | "instance" | "entity"
_entity_cache: dict[tuple[str, str], tuple[str, np.ndarray]] = {}


def _normalize(name: str) -> str:
    """Normalize name for comparison: lowercase, strip, replace hyphens/underscores, remove possessives, lemmatize."""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[-_]", " ", s)
    s = re.sub(r"'s\b", "", s)
    s = " ".join(s.split())
    try:
        import nltk

        _nltk_data = os.environ.get("NLTK_DATA") or str(Path("/tmp/nltk_data").resolve())
        if _nltk_data not in nltk.data.path:
            nltk.data.path.insert(0, _nltk_data)
        try:
            nltk.data.find("corpora/wordnet")
        except LookupError:
            nltk.download("wordnet", quiet=True)
        from nltk.stem import WordNetLemmatizer
        lemmatizer = WordNetLemmatizer()
        tokens = s.split()
        lemmatized = [lemmatizer.lemmatize(t) for t in tokens]
        return " ".join(lemmatized)
    except Exception as e:
        logger.debug("[Canonicalizer] Lemmatization skipped: %s", e)
        return s


def _cache_key(normalized: str, kind: str) -> tuple[str, str]:
    """Return cache key: (normalized, kind). kind separates class vs instance so same surface form can differ."""
    k = (kind or "entity").lower()
    if k not in ("class", "instance"):
        k = "entity"
    return (normalized, k)


def canonicalize(entity_name: str, kind: str = "entity") -> str:
    """Return canonical form: existing similar entity or new (added to cache).

    Uses normalization pre-pass: exact normalized match merges without embedding.
    Otherwise embeds normalized form and compares to SIMILARITY_THRESHOLD.
    kind: "class" | "instance" | "entity" — class and instance use separate namespaces so
    e.g. "Bank" (concept) and "Bank" (entity) can map to different canonical forms.
    """
    name = entity_name.strip()
    if not name:
        return name

    normalized = _normalize(name)
    if not normalized:
        return name

    key = _cache_key(normalized, kind)
    model = get_embedding_model()
    with _lock:
        # Exact normalized match for this kind: always merge (skip embedding cost)
        if key in _entity_cache:
            canonical_display, _ = _entity_cache[key]
            logger.debug("[Canonicalizer] %r -> %r (exact normalized match, kind=%s)", name, canonical_display, key[1])
            return canonical_display

        emb = model.encode(normalized, convert_to_numpy=True, show_progress_bar=False)

        threshold = get_settings().similarity_threshold if get_settings().similarity_threshold is not None else SIMILARITY_THRESHOLD
        for (norm_key, k), (canonical_display, vec) in _entity_cache.items():
            if k != key[1]:
                continue
            sim = np.dot(emb, vec) / (np.linalg.norm(emb) * np.linalg.norm(vec) + 1e-9)
            if sim >= threshold:
                logger.debug("[Canonicalizer] %r -> %r (sim=%.3f, kind=%s)", name, canonical_display, sim, k)
                return canonical_display

        # Store by (normalized, kind); keep display name in original casing (use input name as canonical)
        _entity_cache[key] = (name, emb)
        logger.debug("[Canonicalizer] New entity added to cache: %r | kind=%s | cache_size=%d", name, key[1], len(_entity_cache))
        return name


def canonicalize_batch(
    names: list[str],
    kind: str = "entity",
    batch_size: int | None = None,
) -> list[str]:
    """Canonicalize a list of names in batches (single encode call per batch for speed).

    Returns list of canonical names in same order as names. Uses config canonicalizer_batch_size
    if batch_size is None.
    """
    if not names:
        return []
    batch_size = batch_size or max(1, get_settings().canonicalizer_batch_size)
    key_kind = _cache_key("", kind)[1]
    result: list[str | None] = [None] * len(names)
    to_embed: list[tuple[int, str, str]] = []  # (index, name, normalized)

    with _lock:
        for i, name in enumerate(names):
            n = (name or "").strip()
            if not n:
                result[i] = name
                continue
            normalized = _normalize(n)
            if not normalized:
                result[i] = n
                continue
            key = (normalized, key_kind)
            if key in _entity_cache:
                canonical, _ = _entity_cache[key]
                result[i] = canonical
                continue
            to_embed.append((i, n, normalized))

    if not to_embed:
        return [r or "" for r in result]

    unique_norm = list(dict.fromkeys(t[2] for t in to_embed))
    model = get_embedding_model()
    threshold = get_settings().similarity_threshold if get_settings().similarity_threshold is not None else SIMILARITY_THRESHOLD
    norm_to_emb: dict[str, np.ndarray] = {}
    for start in range(0, len(unique_norm), batch_size):
        batch_norms = unique_norm[start : start + batch_size]
        embs = model.encode(batch_norms, convert_to_numpy=True, show_progress_bar=False)
        if hasattr(embs, "ndim") and embs.ndim == 1:
            embs = np.expand_dims(embs, 0)
        for j, norm in enumerate(batch_norms):
            norm_to_emb[norm] = embs[j]

    with _lock:
        for i, n, normalized in to_embed:
            emb = norm_to_emb.get(normalized)
            if emb is None:
                result[i] = n
                continue
            key = (normalized, key_kind)
            if key in _entity_cache:
                canonical, _ = _entity_cache[key]
                result[i] = canonical
                continue
            canonical_found = None
            for (_, k), (canonical_display, vec) in _entity_cache.items():
                if k != key_kind:
                    continue
                sim = float(np.dot(emb, vec) / (np.linalg.norm(emb) * np.linalg.norm(vec) + 1e-9))
                if sim >= threshold:
                    canonical_found = canonical_display
                    break
            if canonical_found is not None:
                result[i] = canonical_found
            else:
                _entity_cache[key] = (n, emb)
                result[i] = n

    return [r if r is not None else "" for r in result]


def seed_from_entities(entity_names: list[str], kind: str = "entity") -> None:
    """Pre-populate the canonicalizer cache with known entity names.

    Call when loading a KB so that enrichment matches against existing entities.
    Ensures consistent canonicalization across restarts.
    kind: "class" | "instance" | "entity" for namespace.
    """
    if not entity_names:
        return
    key_kind = _cache_key("", kind)[1]
    model = get_embedding_model()
    with _lock:
        for name in entity_names:
            n = (name or "").strip()
            if not n:
                continue
            norm = _normalize(n)
            key = (norm, key_kind)
            if key in _entity_cache:
                continue
            emb = model.encode(norm, convert_to_numpy=True, show_progress_bar=False)
            _entity_cache[key] = (n, emb)
        logger.debug("[Canonicalizer] Seeded %d entities | kind=%s | cache_size=%d", len(entity_names), key_kind, len(_entity_cache))
