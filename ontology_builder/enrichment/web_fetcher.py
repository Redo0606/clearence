"""Search each query via ddgs (Bing backend for Docker compatibility),
then fetch page text and attach a fidelity score.

Scoring:
- fidelity: URL-domain heuristic (academic=1.0, docs=0.85, forums=0.30, etc.)
- content_score: optional LLM-based objective rating (relevance + quality, 0–1)
- combined_score: 0.5*fidelity + 0.5*content_score when content_score present, else fidelity
"""

from __future__ import annotations

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

# ---------- fidelity ----------

_FIDELITY_RULES = [
    # (score, compiled-regex-on-netloc)
    (1.00, re.compile(r"(arxiv\.org|pubmed|\.edu|doi\.org|ncbi\.nlm\.nih)", re.I)),
    (0.85, re.compile(r"(docs\.|readthedocs|wiki\.|wikipedia\.org|\.gov)", re.I)),
    (0.80, re.compile(r"(fandom\.com|gamepedia|wikia\.com)", re.I)),  # gaming wikis
    (0.75, re.compile(r"(gitlab\.com|github\.com|bitbucket\.org)", re.I)),
    (0.60, re.compile(r"(medium\.com|substack\.com)", re.I)),
    (0.45, re.compile(r"(blog\.|wordpress\.com|blogspot\.com)", re.I)),
    (0.30, re.compile(r"(reddit\.com|stackoverflow\.com|stackexchange\.com|quora\.com|discord)", re.I)),
]
_DEFAULT_FIDELITY = 0.15

def fidelity_score(url: str) -> float:
    netloc = urlparse(url).netloc.lower()
    for score, pattern in _FIDELITY_RULES:
        if pattern.search(netloc):
            return score
    return _DEFAULT_FIDELITY


# ---------- LLM content scoring (batched) ----------

PAGE_CONTENT_SCORE_SYSTEM = """You objectively rate a web page's value for ontology enrichment.

Given a search query and the page's title + content excerpt, score 0–1 based on:
1. RELEVANCE: Does the content directly address the query? (0.5 weight)
2. QUALITY: Is it factual, well-structured, and authoritative? (0.3 weight)
3. DEPTH: Does it provide substantive information vs shallow/ads/noise? (0.2 weight)

Be strict: generic landing pages, paywalls, login-only content, or off-topic pages = low score.
Academic, documentation, and detailed explanatory content = high score.

Output ONLY a single decimal between 0 and 1 (e.g. 0.7). Nothing else."""


def _parse_content_score(text: str) -> float:
    """Extract 0–1 score from LLM response."""
    if not text:
        return 0.0
    text = str(text).strip()
    for pattern in [r"1\.0\b", r"0\.[0-9]+", r"\b1\b", r"\b0\b"]:
        m = re.search(pattern, text)
        if m:
            return max(0.0, min(1.0, float(m.group())))
    return 0.0


def score_pages_content_batch(
    pages: list["WebPage"],
    content_snippet_chars: int = 2000,
    progress_callback=None,
    cancel_check=None,
) -> list[float]:
    """
    Batch-score pages via LLM: relevance to query + content quality.
    Returns list of scores (0–1) in same order as pages.
    """
    if not pages:
        return []

    try:
        from ontology_builder.llm.client import complete_batch
    except ImportError:
        logger.warning("[WebFetcher] LLM client not available; skipping content scoring")
        return [0.0] * len(pages)

    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    items = []
    for p in pages:
        snippet = (p.content or "")[:content_snippet_chars]
        items.append((p.query, p.title, p.url, snippet))

    def system_fn(_) -> str:
        return PAGE_CONTENT_SCORE_SYSTEM

    def user_fn(item: tuple) -> str:
        query, title, url, snippet = item
        return f"""Query: {query}

Page title: {title}
URL: {url}

Content excerpt:
{snippet[:1500] if snippet else "(no content)"}

Score (0–1):"""

    _progress("web_content_score_start", {"count": len(pages)})
    if cancel_check and cancel_check():
        return [0.0] * len(pages)

    results = complete_batch(
        items,
        system_fn=system_fn,
        user_fn=user_fn,
        temperature=0.0,
        max_tokens=10,
    )

    scores = [_parse_content_score(r) for r in results]
    _progress("web_content_score_done", {"scores": scores})
    logger.info("[WebFetcher] Content scores: %s", [round(s, 2) for s in scores])
    return scores


# ---------- search (ddgs with Bing backend for Docker) ----------

_HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
_DELAY    = 1.5   # seconds between queries
_MAX_RESULTS = 15


def _web_search(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """
    Search via ddgs. Uses Bing backend for reliable access from Docker/Mac.
    Returns list of {url, title}.
    """
    backends = ["bing", "duckduckgo", "brave"]  # Bing first: works from Docker; fallbacks
    for backend in backends:
        try:
            logger.info("[WebFetcher] Searching (%s) for '%s'", backend, query[:60])
            raw = DDGS(timeout=20).text(query, backend=backend, max_results=max_results)
            results = []
            for r in raw:
                href = r.get("href") or r.get("url") or r.get("link", "")
                if not href.startswith("http"):
                    continue
                title = r.get("title", "") or href
                results.append({"url": href, "title": title})
                if len(results) >= max_results:
                    break
            if results:
                logger.info("[WebFetcher] %s returned %d results for '%s'", backend, len(results), query[:50])
                return results[:max_results]
        except Exception as e:
            logger.warning("[WebFetcher] %s search failed for '%s': %s", backend, query[:50], e)
            continue
    logger.warning("[WebFetcher] All backends failed for '%s'", query[:50])
    return []


# ---------- page fetch ----------

def _is_429(exc):
    return (isinstance(exc, requests.HTTPError)
            and getattr(getattr(exc, "response", None), "status_code", None) == 429)

@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=2, max=20),
       retry=retry_if_exception(_is_429))
def _fetch_page(url: str) -> str:
    domain = urlparse(url).netloc
    logger.info("[WebFetcher] Fetching page: %s | %s", domain, url[:70])
    resp = requests.get(url, headers=_HEADERS, timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    content = text.strip()[:8000]   # hard cap per page to keep doc manageable
    logger.info("[WebFetcher] Fetched %d chars from %s", len(content), domain)
    return content


# ---------- public API ----------

@dataclass
class WebPage:
    query         : str
    url           : str
    title         : str
    content       : str
    fidelity      : float   # URL-domain heuristic (0–1)
    content_score : float | None = None  # LLM-based relevance+quality (0–1), None if not computed
    error         : str = ""

    def combined_score(self, fidelity_weight: float = 0.5) -> float:
        """Objective score: blend fidelity (domain) and content_score (LLM)."""
        if self.content_score is not None:
            return fidelity_weight * self.fidelity + (1 - fidelity_weight) * self.content_score
        return self.fidelity

def _cancellable_sleep(seconds: float, cancel_check=None) -> bool:
    """Sleep for up to seconds, checking cancel every 0.2s. Returns True if cancelled."""
    if not cancel_check:
        time.sleep(seconds)
        return False
    end = time.time() + seconds
    while time.time() < end:
        if cancel_check():
            return True
        time.sleep(0.2)
    return False


def fetch_and_score(queries: list[str], min_fidelity: float = 0.3,
                    results_per_query: int = 8,
                    use_llm_content_score: bool = True,
                    progress_callback=None, cancel_check=None) -> list[WebPage]:
    """
    For each query: search → filter by fidelity → fetch top pages.
    Optionally batch-score pages via LLM for objective relevance+quality rating.

    progress_callback(step, data): optional; step in ("web_fetch_query", "web_fetch_page", "web_content_score_*").
    """
    pages: list[WebPage] = []
    seen_urls: set[str]  = set()
    total_queries = len(queries)

    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    for q_idx, query in enumerate(queries):
        if cancel_check and cancel_check():
            logger.info("[WebFetcher] Cancelled at query %d/%d", q_idx + 1, total_queries)
            break
        remaining_queries = total_queries - (q_idx + 1)
        _progress("web_fetch_query", {
            "query_index": q_idx + 1,
            "total_queries": total_queries,
            "query": query,
            "remaining_queries": remaining_queries,
            "pages_so_far": len(pages),
        })
        logger.info("[WebFetcher] Query %d/%d: %s | %d queries remaining | %d pages so far",
                    q_idx + 1, total_queries, query, remaining_queries, len(pages))

        candidates = _web_search(query, max_results=_MAX_RESULTS)
        if _cancellable_sleep(_DELAY, cancel_check):
            logger.info("[WebFetcher] Cancelled during delay at query %d/%d", q_idx + 1, total_queries)
            break
        logger.info("[WebFetcher] Query '%s': %d results from first page", query[:50], len(candidates))

        for cand in candidates:
            if cancel_check and cancel_check():
                break
            url   = cand["url"]
            score = fidelity_score(url)
            domain = urlparse(url).netloc
            if score < min_fidelity:
                logger.info("[WebFetcher] Skipped (fidelity %.2f < %.2f): %s", score, min_fidelity, domain)
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            _progress("web_fetch_page", {
                "query": query,
                "url": url,
                "title": cand["title"],
                "pages_so_far": len(pages) + 1,
            })
            logger.info("[WebFetcher] Fetching: %s | %s", cand["title"][:50], url[:60])
            try:
                content = _fetch_page(url)
                if _cancellable_sleep(0.5, cancel_check):
                    break
            except Exception as e:
                content = ""
                logger.warning("[WebFetcher] Fetch failed %s: %s", url, e)

            pages.append(WebPage(
                query    = query,
                url      = url,
                title    = cand["title"],
                content  = content,
                fidelity = score,
            ))
            if len([p for p in pages if p.query == query]) >= results_per_query:
                break

    # Fallback: if 0 pages and min_fidelity filters out default sites, retry with lower threshold
    if len(pages) == 0 and min_fidelity > _DEFAULT_FIDELITY and not (cancel_check and cancel_check()):
        logger.info("[WebFetcher] 0 pages with min_fidelity=%.2f, retrying with %.2f", min_fidelity, _DEFAULT_FIDELITY)
        return fetch_and_score(
            queries,
            min_fidelity=_DEFAULT_FIDELITY,
            results_per_query=results_per_query,
            use_llm_content_score=use_llm_content_score,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    # Optional: batched LLM content scoring for objective relevance+quality rating
    if use_llm_content_score and pages and not (cancel_check and cancel_check()):
        content_scores = score_pages_content_batch(
            pages,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        pages = [
            WebPage(
                query=p.query,
                url=p.url,
                title=p.title,
                content=p.content,
                fidelity=p.fidelity,
                content_score=content_scores[i] if i < len(content_scores) else None,
                error=p.error,
            )
            for i, p in enumerate(pages)
        ]

    pages.sort(key=lambda p: p.combined_score(), reverse=True)
    logger.info("[WebFetcher] Done: %d pages from %d queries (sorted by combined_score)", len(pages), total_queries)
    return pages


def fetch_and_score_parallel(
    queries: list[str],
    min_fidelity: float = 0.3,
    results_per_query: int = 3,
    max_search_workers: int = 6,
    max_fetch_workers: int = 8,
    progress_callback=None,
    cancel_check=None,
) -> list[WebPage]:
    """
    Parallel variant: run all searches concurrently, then all page fetches concurrently.
    Optimized for gap repair (no LLM content scoring, fewer pages per query).
    """
    if not queries:
        return []

    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    # Phase 1: parallel search
    _progress("web_fetch_query", {"query_index": 0, "total_queries": len(queries), "message": "Searching in parallel"})
    search_results: list[tuple[str, list[dict]]] = []
    with ThreadPoolExecutor(max_workers=min(max_search_workers, len(queries))) as ex:
        futures = {ex.submit(_web_search, q, 10): q for q in queries}
        for future in as_completed(futures):
            if cancel_check and cancel_check():
                break
            query = futures[future]
            try:
                cands = future.result()
                search_results.append((query, cands))
            except Exception as e:
                logger.warning("[WebFetcher] Parallel search failed for %s: %s", query[:50], e)
                search_results.append((query, []))

    # Build (query, url, title, fidelity) candidates, filter by fidelity
    candidates: list[tuple[str, str, str, float]] = []
    seen_urls: set[str] = set()
    for query, cands in search_results:
        for c in cands:
            url = (c.get("href") or c.get("url") or c.get("link") or "").strip()
            if not url.startswith("http") or url in seen_urls:
                continue
            score = fidelity_score(url)
            if score < min_fidelity:
                continue
            seen_urls.add(url)
            title = c.get("title", "") or url
            candidates.append((query, url, title, score))
            if len([x for x in candidates if x[0] == query]) >= results_per_query:
                break

    # Cap per-query
    per_query: dict[str, int] = {}
    filtered: list[tuple[str, str, str, float]] = []
    for q, u, t, s in candidates:
        per_query[q] = per_query.get(q, 0) + 1
        if per_query[q] <= results_per_query:
            filtered.append((q, u, t, s))

    if not filtered:
        if min_fidelity > _DEFAULT_FIDELITY:
            return fetch_and_score_parallel(
                queries, min_fidelity=_DEFAULT_FIDELITY,
                results_per_query=results_per_query,
                max_search_workers=max_search_workers,
                max_fetch_workers=max_fetch_workers,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
        return []

    # Phase 2: parallel page fetch
    _progress("web_fetch_page", {"message": "Fetching pages in parallel", "count": len(filtered)})

    def _fetch_one(item: tuple[str, str, str, float]) -> WebPage:
        query, url, title, fidelity = item
        try:
            content = _fetch_page(url)
        except Exception as e:
            content = ""
            logger.warning("[WebFetcher] Fetch failed %s: %s", url, e)
        return WebPage(query=query, url=url, title=title, content=content, fidelity=fidelity)

    pages: list[WebPage] = []
    with ThreadPoolExecutor(max_workers=max_fetch_workers) as ex:
        futures = {ex.submit(_fetch_one, item): item for item in filtered}
        for future in as_completed(futures):
            if cancel_check and cancel_check():
                break
            try:
                pages.append(future.result())
            except Exception as e:
                logger.warning("[WebFetcher] Parallel fetch failed: %s", e)

    pages.sort(key=lambda p: p.fidelity, reverse=True)
    logger.info("[WebFetcher] Parallel done: %d pages from %d queries", len(pages), len(queries))
    return pages
