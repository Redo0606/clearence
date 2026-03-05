"""Split text into overlapping chunks for LLM extraction."""

import logging

logger = logging.getLogger(__name__)


def chunk_text(text: str, size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for LLM context.

    Args:
        text: Input text to chunk.
        size: Chunk size in characters.
        overlap: Overlap between consecutive chunks.

    Returns:
        List of chunk strings. Empty if text is empty or size <= 0.
    """
    logger.debug("[Chunker] Chunking | text_len=%d | size=%d | overlap=%d", len(text), size, overlap)
    text = text.strip() if text else ""
    if not text or size <= 0:
        logger.debug("[Chunker] Empty text or invalid size, returning []")
        return []
    if overlap >= size:
        overlap = max(0, size - 1)
        logger.debug("[Chunker] Adjusted overlap to %d", overlap)

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + size
        chunk = text[start:end]
        chunks.append(chunk)
        start += size - overlap

    logger.info("[Chunker] Created %d chunks | avg_len=%.0f", len(chunks), sum(len(c) for c in chunks) / len(chunks) if chunks else 0)
    return chunks
