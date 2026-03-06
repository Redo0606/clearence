"""Shared embedding backend: SentenceTransformer (local) or OpenAI batched (same LLM stack).

Loaded once per process; all consumers use the same instance. When using OpenAI,
embeddings use the same openai_base_url and openai_api_key as the LLM, with
batched calls (embedding_openai_batch_size) for throughput.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, List, Union

import numpy as np

from core.config import (
    EMBEDDING_PROVIDER_OPENAI,
    EMBEDDING_PROVIDER_SENTENCE_TRANSFORMERS,
    get_settings,
)

logger = logging.getLogger(__name__)

_model: Any = None
_lock = threading.Lock()

# SentenceTransformer default (all-MiniLM-L6-v2 has 384 dims).
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"

# Known OpenAI embedding dimensions (for pre-alloc and cache).
_OPENAI_EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class _OpenAIEmbeddingBackend:
    """OpenAI embeddings via batched API calls using the same base URL and API key as the LLM."""

    def __init__(self) -> None:
        from openai import OpenAI

        settings = get_settings()
        api_key = settings.get_llm_api_key()
        base_url = (settings.openai_base_url or "").strip()
        if "api.openai.com" in base_url.lower() and not (api_key and api_key.strip()):
            raise ValueError(
                "OPENAI_API_KEY is required for OpenAI embeddings when using api.openai.com. "
                "Set OPENAI_API_KEY in .env or use embedding_provider=sentence_transformers."
            )
        self._client = OpenAI(api_key=api_key, base_url=settings.openai_base_url)
        self._model = settings.embedding_openai_model
        self._batch_size = max(1, min(2048, settings.embedding_openai_batch_size))

    @property
    def embedding_dimension(self) -> int:
        return _OPENAI_EMBEDDING_DIMS.get(
            self._model,
            1536,
        )

    def encode(
        self,
        texts: Union[str, List[str]],
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        if not texts:
            dim = self.embedding_dimension
            if single:
                return np.zeros(dim, dtype=np.float32)
            return np.zeros((0, dim), dtype=np.float32)
        # Batched calls: OpenAI rejects empty strings and control chars in input; sanitize each item
        _control = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

        def _sanitize(s: str) -> str:
            t = str(s).strip() if s is not None else ""
            if not t:
                return " "
            return _control.sub(" ", t)

        all_embs: list[np.ndarray] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            sanitized = [_sanitize(t) for t in batch]
            resp = self._client.embeddings.create(input=sanitized, model=self._model)
            # Preserve order (API returns data with index matching input order)
            sorted_data = sorted(resp.data, key=lambda d: d.index)
            vecs = np.array([d.embedding for d in sorted_data], dtype=np.float32)
            if normalize_embeddings:
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                vecs = vecs / norms
            all_embs.append(vecs)
        out = np.vstack(all_embs)
        if single:
            out = out[0]
        return out


def _get_sentence_transformer_dimension() -> int:
    """Return dimension for the default SentenceTransformer model (384 for MiniLM-L6-v2)."""
    return 384


def get_embedding_dimension() -> int:
    """Return the embedding dimension of the currently configured backend (384 for ST, 1536/3072 for OpenAI)."""
    settings = get_settings()
    if settings.embedding_provider == EMBEDDING_PROVIDER_OPENAI:
        # Avoid loading the model just for dimension; use known dims.
        return _OPENAI_EMBEDDING_DIMS.get(settings.embedding_openai_model, 1536)
    return _get_sentence_transformer_dimension()


def get_embedding_model() -> Any:
    """Return the shared embedding backend (SentenceTransformer or OpenAI batched), loading once if needed (thread-safe)."""
    global _model
    settings = get_settings()
    with _lock:
        if _model is None:
            if settings.embedding_provider == EMBEDDING_PROVIDER_OPENAI:
                logger.info(
                    "Embeddings via OpenAI (batched) | model=%s | batch_size=%d | base_url=%s",
                    settings.embedding_openai_model,
                    settings.embedding_openai_batch_size,
                    settings.openai_base_url,
                )
                _model = _OpenAIEmbeddingBackend()
            else:
                logger.info(
                    "Load pretrained SentenceTransformer: %s",
                    SENTENCE_TRANSFORMER_MODEL,
                )
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
        return _model


def preload_embedding_model() -> None:
    """Force-load the shared model (e.g. at app startup) so first request does not pay load cost."""
    get_embedding_model()
