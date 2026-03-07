"""
Build a Markdown document from fetched web pages.
Each section is:  ## Title  |  Source: URL  |  Fidelity: X.XX  |  raw content
"""

import hashlib
import logging
import time
from pathlib import Path

_OUT_DIR = Path(__file__).resolve().parent.parent.parent / "documents" / "enrichment"

_FIDELITY_LABEL = {
    1.00: "research",
    0.85: "documentation",
    0.75: "gitlab/github",
    0.60: "verified-blog",
    0.45: "blog",
    0.30: "forum",
    0.15: "post",
}


def _label(score: float) -> str:
    thresholds = sorted(_FIDELITY_LABEL.keys(), reverse=True)
    for t in thresholds:
        if score >= t:
            return _FIDELITY_LABEL[t]
    return "post"


def build_document(pages, prefix: str = "web_enrichment",
                   progress_callback=None, cancel_check=None) -> Path:
    """
    Args:
        pages  : list[WebPage]
        prefix : filename prefix
        progress_callback : optional (step, data) for UI; step in ("web_build_section",)

    Returns:
        Path to the written .md file
    """
    logger = logging.getLogger(__name__)

    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # deterministic name based on content hash
    digest  = hashlib.md5("".join(p.url for p in pages).encode()).hexdigest()[:8]
    ts      = int(time.time())
    outpath = _OUT_DIR / f"{prefix}_{ts}_{digest}.md"

    lines = [
        f"# Web Enrichment Document",
        f"",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"Sources: {len(pages)} pages  ",
        f"",
    ]

    total_pages = len(pages)
    for p_idx, page in enumerate(pages):
        if cancel_check and cancel_check():
            logger.info("[DocBuilder] Cancelled at section %d/%d", p_idx + 1, total_pages)
            break
        remaining = total_pages - (p_idx + 1)
        _progress("web_build_section", {
            "page_index": p_idx + 1,
            "total_pages": total_pages,
            "title": page.title,
            "url": page.url,
            "query": page.query,
            "remaining_pages": remaining,
        })
        logger.info("[DocBuilder] Section %d/%d: %s | %d remaining", p_idx + 1, total_pages, page.title[:50], remaining)
        label = _label(page.fidelity)
        score_parts = [f"**Fidelity:** {page.fidelity:.2f} ({label})"]
        if page.content_score is not None:
            score_parts.append(f"**Content score:** {page.content_score:.2f}")
            score_parts.append(f"**Combined:** {page.combined_score():.2f}")
        lines += [
            f"## {page.title}",
            f"",
            f"**Source:** {page.url}  ",
            "  ".join(score_parts) + "  ",
            f"**Query:** {page.query}  ",
            f"",
            page.content if page.content else "_Content not available._",
            f"",
            "---",
            "",
        ]

    outpath.write_text("\n".join(lines), encoding="utf-8")
    return outpath
