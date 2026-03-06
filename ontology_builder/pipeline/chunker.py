"""Split text into overlapping chunks for LLM extraction.

Supports fixed-window (legacy) and semantic (sentence-boundary) chunking.
Sentence splitting uses pysbd (rule-based, no NLTK); handles abbreviations, decimals, etc.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

# Lazy-instantiate pysbd segmenter (one per process)
_segmenter = None

def _get_segmenter():
    global _segmenter
    if _segmenter is None:
        logger.debug("[Chunker] Loading pysbd segmenter")
        import pysbd
        _segmenter = pysbd.Segmenter(language="en", clean=False)
    return _segmenter


def _sent_tokenize(text: str) -> list[str]:
    """Split text into sentences using pysbd (abbreviations, decimals, etc.). No NLTK."""
    if not text or not text.strip():
        return []
    try:
        seg = _get_segmenter()
        sentences = seg.segment(text)
        return [s.strip() for s in sentences if s.strip()]
    except Exception as e:
        logger.warning("[Chunker] pysbd failed (%s), falling back to regex split", e)
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]


def chunk_text_semantic(text: str, size: int = 2000, overlap: int = 300) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Greedily accumulates sentences until character count approaches size,
    then backtracks overlap characters worth of sentences to start the next chunk.
    """
    text = text.strip() if text else ""
    if not text or size <= 0:
        return []
    if overlap >= size:
        overlap = max(0, size - 1)

    logger.info("[Chunker] Splitting into sentences...")
    sentences = _sent_tokenize(text)
    logger.info("[Chunker] Got %d sentences | building chunks (size=%d, overlap=%d)", len(sentences), size, overlap)
    if not sentences:
        return [text[: size]] if len(text) > size else ([text] if text else [])

    chunks: list[str] = []
    start_idx = 0
    log_every_n = 10  # log progress every N chunks

    while start_idx < len(sentences):
        acc: list[str] = []
        char_count = 0
        i = start_idx
        while i < len(sentences):
            s = sentences[i]
            need = len(s) + (1 if acc else 0)
            if char_count + need > size and acc:
                break
            acc.append(s)
            char_count += need
            i += 1
        if not acc:
            acc = [sentences[start_idx]]
            start_idx += 1
        else:
            chunk_str = " ".join(acc)
            chunks.append(chunk_str)
            if len(chunks) % log_every_n == 0:
                logger.info("[Chunker] Built %d chunks so far (sentence %d/%d)", len(chunks), start_idx + len(acc), len(sentences))
            # Backtrack: number of sentences to re-include for overlap
            overlap_chars = 0
            n_overlap = 0
            for j in range(len(acc) - 1, -1, -1):
                if overlap_chars >= overlap:
                    break
                n_overlap += 1
                overlap_chars += len(acc[j]) + (1 if j < len(acc) - 1 else 0)
            next_start = start_idx + len(acc) - n_overlap
            # Always advance by at least one sentence to avoid infinite loop when a single sentence exceeds size
            start_idx = max(next_start, start_idx + 1)
            if start_idx >= len(sentences):
                break

    logger.info(
        "[Chunker] Semantic: %d chunks | avg_len=%.0f",
        len(chunks),
        sum(len(c) for c in chunks) / len(chunks) if chunks else 0,
    )
    return chunks


def chunk_text_fixed(text: str, size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into fixed-size overlapping windows (legacy behavior)."""
    logger.info("[Chunker] Fixed window | text_len=%d | size=%d | overlap=%d", len(text or ""), size, overlap)
    text = text.strip() if text else ""
    if not text or size <= 0:
        return []
    if overlap >= size:
        overlap = max(0, size - 1)
    chunks = []
    start = 0
    log_every_n = 20
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if len(chunks) % log_every_n == 0:
            logger.info("[Chunker] Fixed: built %d chunks so far", len(chunks))
        start += size - overlap
    logger.info("[Chunker] Fixed: %d chunks | avg_len=%.0f", len(chunks), sum(len(c) for c in chunks) / len(chunks) if chunks else 0)
    return chunks


def chunk_text(
    text: str,
    size: int = 2000,
    overlap: int = 300,
    mode: Literal["fixed", "semantic"] = "semantic",
) -> list[str]:
    """Split text into overlapping chunks for LLM context.

    Args:
        text: Input text to chunk.
        size: Target chunk size in characters.
        overlap: Overlap between consecutive chunks (chars for fixed; approximate for semantic).
        mode: "semantic" (default) uses sentence boundaries; "fixed" uses sliding window.

    Returns:
        List of chunk strings. Empty if text is empty or size <= 0.
    """
    logger.info("[Chunker] Starting | mode=%s | text_len=%d", mode, len(text or ""))
    if mode == "fixed":
        return chunk_text_fixed(text, size=size, overlap=overlap)
    try:
        return chunk_text_semantic(text, size=size, overlap=overlap)
    except Exception as e:
        logger.warning("[Chunker] Semantic chunking failed (%s), falling back to fixed", e)
        return chunk_text_fixed(text, size=size, overlap=overlap)
