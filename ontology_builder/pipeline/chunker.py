"""Split text into overlapping chunks for LLM extraction.

Uses sentence-boundary chunking: never splits mid-sentence. Optionally detects
section boundaries (Markdown headings, DOCX-style headers) to avoid context bleed.
Falls back to fixed character-window when sentence splitting yields fewer than 2 chunks.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from core.config import get_settings

logger = logging.getLogger(__name__)


def _sent_tokenize_simple(text: str) -> list[str]:
    """Split text into sentences using regex. No NLTK/spacy — stays within existing deps.

    Splits on ". ", "? ", "! " followed by capital letter or start of line.
    """
    if not text or not text.strip():
        return []
    # Split on sentence-ending punctuation followed by whitespace and capital letter
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def _detect_section_boundaries(lines: list[str]) -> list[int]:
    """Return indices of lines that start a new section.

    Rules (apply in order):
    - Markdown: lines starting with #, ##, ###
    - DOCX headings: lines that are ALL CAPS and under 80 chars, or lines ending with colon at paragraph start
    - PDF titles: lines under 60 chars with no sentence-ending punctuation followed by a blank line
    """
    boundaries: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Markdown headings
        if re.match(r"^#{1,6}\s", stripped):
            boundaries.append(i)
            continue
        # DOCX: ALL CAPS under 80 chars (excluding punctuation)
        if len(stripped) <= 80 and stripped.isupper() and any(c.isalpha() for c in stripped):
            boundaries.append(i)
            continue
        # DOCX: line ending with colon at start of paragraph (preceded by blank or start)
        if stripped.endswith(":") and (i == 0 or not lines[i - 1].strip()):
            boundaries.append(i)
            continue
        # PDF-style title: short line, no .!? at end, followed by blank
        if len(stripped) <= 60 and not re.search(r"[.!?]\s*$", stripped):
            if i + 1 < len(lines) and not lines[i + 1].strip():
                boundaries.append(i)
    return boundaries


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (header, content) sections. Returns [(header, content), ...]."""
    lines = text.splitlines()
    boundaries = _detect_section_boundaries(lines)
    if not boundaries:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    for j, start in enumerate(boundaries):
        end = boundaries[j + 1] if j + 1 < len(boundaries) else len(lines)
        section_lines = lines[start:end]
        header = section_lines[0] if section_lines else ""
        content = "\n".join(section_lines)
        sections.append((header, content))
    return sections


def chunk_text_semantic(
    text: str,
    size: int | None = None,
    overlap: int | None = None,
    detect_sections: bool = True,
) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Sentence-boundary approach: accumulates sentences until adding the next would
    exceed size. Overlap is implemented by re-including the last N sentences from
    the previous chunk (where N uses the overlap character budget). Never splits
    a sentence across chunks.

    When detect_sections is True, section boundaries (Markdown ##, DOCX headings,
    etc.) force a new chunk to start, preventing context bleed between topics.
    """
    settings = get_settings()
    size = size if size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    text = text.strip() if text else ""
    if not text or size <= 0:
        return []
    if overlap >= size:
        overlap = max(0, size - 1)

    chunks: list[str] = []

    if detect_sections:
        sections = _split_into_sections(text)
        for header, content in sections:
            if not content.strip():
                continue
            sents = _sent_tokenize_simple(content)
            if not sents:
                if content.strip():
                    chunks.append(content.strip())
                continue
            _accumulate_sentences(sents, size, overlap, chunks)
            # Ensure section header starts next chunk if we have multiple sections
            if header and chunks and not chunks[-1].startswith(header):
                pass  # header is already in content; chunking handled it
    else:
        sents = _sent_tokenize_simple(text)
        if not sents:
            return [text[:size]] if len(text) > size else ([text] if text else [])
        _accumulate_sentences(sents, size, overlap, chunks)

    # Fallback: if sentence splitting produced fewer than 2 chunks, use fixed window
    if len(chunks) < 2 and text:
        logger.debug("[Chunker] Sentence splitting produced %d chunk(s), falling back to fixed window", len(chunks))
        return chunk_text_fixed(text, size=size, overlap=overlap)

    logger.info(
        "[Chunker] Semantic: %d chunks | avg_len=%.0f",
        len(chunks),
        sum(len(c) for c in chunks) / len(chunks) if chunks else 0,
    )
    return chunks


def _accumulate_sentences(sentences: list[str], size: int, overlap: int, chunks: list[str]) -> None:
    """Accumulate sentences into chunks, mutating chunks in place."""
    start_idx = 0
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
            # Overlap: how many sentences from end to re-include
            overlap_chars = 0
            n_overlap = 0
            for j in range(len(acc) - 1, -1, -1):
                if overlap_chars >= overlap:
                    break
                n_overlap += 1
                overlap_chars += len(acc[j]) + (1 if j < len(acc) - 1 else 0)
            next_start = start_idx + len(acc) - n_overlap
            start_idx = max(next_start, start_idx + 1)
            if start_idx >= len(sentences):
                break


def chunk_text_fixed(text: str, size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into fixed-size overlapping windows (legacy fallback)."""
    logger.info("[Chunker] Fixed window | text_len=%d | size=%d | overlap=%d", len(text or ""), size, overlap)
    text = text.strip() if text else ""
    if not text or size <= 0:
        return []
    if overlap >= size:
        overlap = max(0, size - 1)
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    logger.info("[Chunker] Fixed: %d chunks | avg_len=%.0f", len(chunks), sum(len(c) for c in chunks) / len(chunks) if chunks else 0)
    return chunks


def chunk_text(
    text: str,
    size: int | None = None,
    overlap: int | None = None,
    mode: Literal["fixed", "semantic"] = "semantic",
    detect_sections: bool = True,
) -> list[str]:
    """Split text into overlapping chunks for LLM context.

    Uses sentence-boundary chunking by default: never splits mid-sentence.
    When detect_sections is True, section headers (Markdown ##, DOCX headings)
    force new chunks to avoid context bleed. Falls back to fixed character window
    when sentence splitting yields fewer than 2 chunks.

    Args:
        text: Input text to chunk.
        size: Target chunk size in characters (from config if None).
        overlap: Overlap between consecutive chunks (from config if None).
        mode: "semantic" (default) uses sentence boundaries; "fixed" uses sliding window.
        detect_sections: If True, detect section boundaries and start new chunks there.

    Returns:
        List of chunk strings. Empty if text is empty or size <= 0.
    """
    settings = get_settings()
    size = size if size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    logger.info("[Chunker] Starting | mode=%s | detect_sections=%s | text_len=%d", mode, detect_sections, len(text or ""))
    if mode == "fixed":
        return chunk_text_fixed(text, size=size, overlap=overlap)
    try:
        return chunk_text_semantic(text, size=size, overlap=overlap, detect_sections=detect_sections)
    except Exception as e:
        logger.warning("[Chunker] Semantic chunking failed (%s), falling back to fixed", e)
        return chunk_text_fixed(text, size=size, overlap=overlap)
