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


def _normalize_for_exact(name: str) -> str:
    """Stage 1 normalization: lowercase, strip punctuation, collapse whitespace."""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = " ".join(s.split())
    return s


def _token_overlap_ratio(a: str, b: str) -> float:
    """Stage 2: token overlap ratio. Returns len(A & B) / max(len(A), len(B))."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
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

    3-stage hybrid: Stage 1 exact match, Stage 2 token overlap (>=0.8), Stage 3 embedding similarity.
    kind: "class" | "instance" | "entity" — class and instance use separate namespaces.
    """
    name = entity_name.strip()
    if not name:
        return name

    normalized = _normalize(name)
    if not normalized:
        return name

    norm_exact = _normalize_for_exact(name)
    key = _cache_key(normalized, kind)
    key_kind = key[1]

    with _lock:
        # Stage 1 — String normalization + exact match
        for (norm_key, k), (canonical_display, _) in _entity_cache.items():
            if k != key_kind:
                continue
            other_norm_exact = _normalize_for_exact(canonical_display)
            if norm_exact == other_norm_exact:
                logger.debug("[Canonicalizer] Canonicalized via stage 1: %s -> %s", name, canonical_display)
                return canonical_display

        # Stage 2 — Lexical similarity (token overlap >= 0.8)
        for (norm_key, k), (canonical_display, _) in _entity_cache.items():
            if k != key_kind:
                continue
            overlap = _token_overlap_ratio(norm_exact, _normalize_for_exact(canonical_display))
            if overlap >= 0.8:
                logger.debug("[Canonicalizer] Canonicalized via stage 2: %s -> %s", name, canonical_display)
                return canonical_display

    # Stage 3 — Embedding similarity (existing logic)
    model = get_embedding_model()
    emb = model.encode(normalized, convert_to_numpy=True, show_progress_bar=False)
    threshold = get_settings().similarity_threshold if get_settings().similarity_threshold is not None else SIMILARITY_THRESHOLD

    with _lock:
        if key in _entity_cache:
            canonical_display, _ = _entity_cache[key]
            logger.debug("[Canonicalizer] %r -> %r (exact normalized match, kind=%s)", name, canonical_display, key_kind)
            return canonical_display

        for (_, k), (canonical_display, vec) in _entity_cache.items():
            if k != key_kind:
                continue
            sim = np.dot(emb, vec) / (np.linalg.norm(emb) * np.linalg.norm(vec) + 1e-9)
            if sim >= threshold:
                logger.debug("[Canonicalizer] Canonicalized via stage 3: %s -> %s", name, canonical_display)
                return canonical_display

        _entity_cache[key] = (name, emb)
        logger.debug("[Canonicalizer] New entity added to cache: %r | kind=%s | cache_size=%d", name, key_kind, len(_entity_cache))
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
    # Batched for 10-50x speedup over per-entity encoding
    for start in range(0, len(unique_norm), batch_size):
        batch_norms = unique_norm[start : start + batch_size]
        embs = model.encode(batch_norms, convert_to_numpy=True, show_progress_bar=False)
        if hasattr(embs, "ndim") and embs.ndim == 1:
            embs = np.expand_dims(embs, 0)
        for j, norm in enumerate(batch_norms):
            norm_to_emb[norm] = embs[j]

    with _lock:
        for i, n, normalized in to_embed:
            norm_exact = _normalize_for_exact(n)
            key = (normalized, key_kind)

            # Stage 1 — exact match
            for (_, k), (canonical_display, _) in _entity_cache.items():
                if k != key_kind:
                    continue
                if norm_exact == _normalize_for_exact(canonical_display):
                    result[i] = canonical_display
                    break
            else:
                # Stage 2 — token overlap
                canonical_found = None
                for (_, k), (canonical_display, _) in _entity_cache.items():
                    if k != key_kind:
                        continue
                    if _token_overlap_ratio(norm_exact, _normalize_for_exact(canonical_display)) >= 0.8:
                        canonical_found = canonical_display
                        break
                if canonical_found is not None:
                    result[i] = canonical_found
                else:
                    # Stage 3 — embedding
                    emb = norm_to_emb.get(normalized)
                    if emb is None:
                        result[i] = n
                    elif key in _entity_cache:
                        canonical, _ = _entity_cache[key]
                        result[i] = canonical
                    else:
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


BATCH_SIZE = 128


def seed_from_entities(entity_names: list[str], kind: str = "entity") -> None:
    """Pre-populate the canonicalizer cache with known entity names.

    Call when loading a KB so that enrichment matches against existing entities.
    Ensures consistent canonicalization across restarts.
    kind: "class" | "instance" | "entity" for namespace.
    Uses batch encoding for performance (typical: 3-6s -> <0.5s).
    """
    if not entity_names:
        return
    key_kind = _cache_key("", kind)[1]

    # 1. Normalize and filter already cached
    to_seed: list[tuple[str, str]] = []  # (display_name, normalized)
    with _lock:
        for name in entity_names:
            n = (name or "").strip()
            if not n:
                continue
            norm = _normalize(n)
            key = (norm, key_kind)
            if key in _entity_cache:
                continue
            to_seed.append((n, norm))

    if not to_seed:
        return

    # 2. Batch encode normalized names — Batched for 10-50x speedup over per-entity encoding
    unique_norms = list(dict.fromkeys(t[1] for t in to_seed))
    model = get_embedding_model()
    norm_to_emb: dict[str, np.ndarray] = {}
    for start in range(0, len(unique_norms), BATCH_SIZE):
        batch = unique_norms[start : start + BATCH_SIZE]
        embs = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        if hasattr(embs, "ndim") and embs.ndim == 1:
            embs = np.expand_dims(embs, 0)
        for j, norm in enumerate(batch):
            norm_to_emb[norm] = embs[j]

    # 3. Insert into cache
    with _lock:
        for display_name, norm in to_seed:
            key = (norm, key_kind)
            if key in _entity_cache:
                continue
            emb = norm_to_emb.get(norm)
            if emb is not None:
                _entity_cache[key] = (display_name, emb)
        logger.debug(
            "[Canonicalizer] Seeded %d entities | kind=%s | cache_size=%d",
            len(entity_names),
            key_kind,
            len(_entity_cache),
        )
