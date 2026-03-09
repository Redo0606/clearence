"""
Gap repair: detect concepts without definitions and fetch definitions from the web.

Similar to internet KB enrichment but targeted at filling missing descriptions
for existing graph nodes. Uses web search + LLM extraction to reify definitions.
Optimized: parallel fetch, batched LLM extraction, batched graph updates.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ontology_builder.embeddings import get_embedding_dimension, get_embedding_model
from ontology_builder.enrichment.query_planner import _infer_domain_hint
from ontology_builder.enrichment.web_fetcher import WebPage, fetch_and_score_parallel

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

MAX_GAPS_TO_REPAIR = 15
DEFAULT_MIN_FIDELITY = 0.3
EXTRACT_BATCH_SIZE = 16  # LLM batch size
CONTENT_SNIPPET_CHARS = 4000

# Noise filter: concepts that are likely code/implementation artifacts
_NOISE_PATTERNS = [
    r"^[\d.%]+$",
    r"^[a-z_]+\(.*\)$",  # function calls
    r"^[A-Za-z_]+\.py$",
]
_NOISE_EXACT = frozenset({
    "e", "graph", "node", "type", "name",
    "update_graph", "infer_relations", "update_graph_from_aggregated",
    "document(s) with sse progress", "ontologyclass",
})


def _is_noise_concept(concept: str) -> bool:
    """Filter out concepts that are likely noise or implementation artifacts."""
    if not concept or len(concept) > 60:
        return True
    c = concept.strip().lower()
    if c in _NOISE_EXACT:
        return True
    for pat in _NOISE_PATTERNS:
        if re.match(pat, c):
            return True
    if c.startswith(("_", "get ", "set ", "a ", "an ", "the ")):
        return True
    return False


def _parse_extracted_definition(text: str) -> str | None:
    """Parse LLM extraction output; return None if NONE, empty, or low-quality."""
    if not text:
        return None
    out = text.strip()
    if not out or out.upper() == "NONE":
        return None
    if len(out) < 15:
        return None
    if out.upper().startswith(("I DON'T", "I CANNOT", "I COULD NOT", "UNABLE", "NO ")):
        return None
    return out[:500]


@dataclass
class GapRepairReport:
    """Result of gap repair (internet definition fetch)."""

    gaps_detected: int = 0
    gaps_repaired: int = 0
    queries_run: int = 0
    pages_fetched: int = 0
    definitions_added: dict[str, str] = field(default_factory=dict)


def detect_gaps_in_graph(
    graph: "OntologyGraph",
    kb_path: Path | str | None = None,
    max_gaps: int = MAX_GAPS_TO_REPAIR,
) -> list[str]:
    """Detect ontology gaps: nodes without description (referenced but not defined).

    Args:
        graph: OntologyGraph to scan.
        kb_path: Optional path for domain inference from metadata.
        max_gaps: Maximum number of gaps to return.

    Returns:
        List of node names that lack a description.
    """
    g = graph.get_graph()
    gaps: list[str] = []
    seen_normalized: set[str] = set()

    for node, data in g.nodes(data=True):
        desc = (data.get("description") or "").strip()
        if desc:
            continue
        if _is_noise_concept(node):
            continue
        norm = node.strip().lower()
        if norm in seen_normalized:
            continue
        seen_normalized.add(norm)
        gaps.append(node)
        if len(gaps) >= max_gaps:
            break

    return gaps


def _plan_queries_for_gaps(
    gaps: list[str],
    graph: "OntologyGraph",
    kb_path: Path | str | None,
    domain_hint: str,
) -> list[str]:
    """Build web search queries for each gap: 'what is X definition' + domain."""
    queries: list[str] = []
    for concept in gaps:
        q = f"what is {concept} definition"
        if domain_hint and domain_hint.lower() not in concept.lower():
            q = f"{domain_hint} {q}"
        queries.append(q)
    return queries


def _extract_definitions_batch(
    items: list[tuple[str, WebPage]],
    cancel_check: Callable[[], bool] | None = None,
    domain_hint: str = "",
) -> list[str | None]:
    """Batch-extract definitions via LLM. Returns list of definition or None in same order."""
    if not items:
        return []

    try:
        from ontology_builder.llm.client import complete_batch
    except ImportError:
        return [None] * len(items)

    def system_fn(_) -> str:
        return """You extract domain-specific definitions for ontology enrichment.
Reply with ONLY the definition (1-2 sentences, factual, in-context) or exactly: NONE
- Be explicit and context-aware: include domain relevance when the concept is domain-specific.
- Do NOT add generic filler. If the text does not define or explain the concept, reply NONE."""

    def user_fn(item: tuple[str, WebPage]) -> str:
        concept, page = item
        content = (page.content or "").strip()[:CONTENT_SNIPPET_CHARS]
        if len(content) < 50:
            return f'Concept: "{concept}"\nContent too short.\nNONE'
        domain_ctx = f" (in {domain_hint} context)" if domain_hint else ""
        return f'''Extract a concise 1-2 sentence definition of "{concept}"{domain_ctx} from the following text.
If the text does not define or explain "{concept}", reply with exactly: NONE
Otherwise reply with only the definition, no preamble or quotes. Be explicit and context-aware.

{content}'''

    results = complete_batch(
        items,
        system_fn=system_fn,
        user_fn=user_fn,
        temperature=0.0,
        max_tokens=150,
        parallel=True,
    )
    return [_parse_extracted_definition(r) if r else None for r in results]


def reify_definitions_from_web(
    graph: "OntologyGraph",
    gaps: list[str],
    kb_path: Path | str | None = None,
    min_fidelity: float = DEFAULT_MIN_FIDELITY,
    max_queries: int | None = None,
    progress_callback: Callable[[str, str, dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> GapRepairReport:
    """Search the web for definitions of missing concepts and update the graph.

    Optimized flow: parallel fetch -> batched LLM extraction -> batched graph updates.

    Args:
        graph: OntologyGraph to update (mutated in-place).
        gaps: List of node names without descriptions.
        kb_path: Optional path for domain inference.
        min_fidelity: Minimum URL fidelity score (0-1).
        max_queries: Cap on total queries (default: len(gaps)).
        progress_callback: Optional (step, message, data).
        cancel_check: Optional callable that returns True to abort.

    Returns:
        GapRepairReport with counts and definitions_added.
    """
    report = GapRepairReport(gaps_detected=len(gaps))

    def _progress(step: str, message: str, data: dict | None = None):
        if progress_callback:
            progress_callback(step, message, data or {})

    if not gaps:
        return report

    domain_hint = _infer_domain_hint(graph, kb_path)
    queries = _plan_queries_for_gaps(gaps, graph, kb_path, domain_hint)
    if max_queries:
        queries = queries[:max_queries]
    report.queries_run = len(queries)

    _progress("gap_repair_queries", f"Searching for {len(queries)} definitions (parallel)", {"queries": queries})

    def _cb(step: str, data: dict):
        _progress("gap_repair_fetch", step, data)

    # Parallel fetch (no delays between queries)
    pages = fetch_and_score_parallel(
        queries,
        min_fidelity=min_fidelity,
        results_per_query=3,
        progress_callback=_cb,
        cancel_check=cancel_check,
    )
    report.pages_fetched = len(pages)

    if cancel_check and cancel_check():
        return report

    concept_to_query = {gaps[i]: queries[i] for i in range(min(len(queries), len(gaps)))}
    concept_to_pages: dict[str, list[WebPage]] = {}
    for concept in gaps:
        q = concept_to_query.get(concept, f"what is {concept} definition")
        exact = [p for p in pages if p.query == q]
        if exact:
            concept_to_pages[concept] = exact
        else:
            # Fallback: match by concept name in query (handles slight query variations)
            fallback = [p for p in pages if concept in p.query or (concept.lower() in p.query.lower())]
            concept_to_pages[concept] = fallback
    pages_with_content = sum(1 for p in pages if p.content and len((p.content or "").strip()) >= 50)
    logger.info("[GapRepair] %d pages fetched, %d with content>=50; concepts with pages: %d/%d",
                len(pages), pages_with_content, sum(1 for c in gaps if concept_to_pages.get(c)), len(gaps))

    # Build batch items: (concept, page) for all concepts, one page per concept first
    batch_items: list[tuple[str, WebPage]] = []
    for concept in gaps:
        for page in concept_to_pages.get(concept, [])[:3]:
            if page.content and len(page.content.strip()) >= 50:
                batch_items.append((concept, page))
                break  # one page per concept per batch round

    concept_definitions: dict[str, str] = {}
    processed_concepts: set[str] = set()

    # Batch extract in chunks
    for i in range(0, len(batch_items), EXTRACT_BATCH_SIZE):
        if cancel_check and cancel_check():
            break
        chunk = batch_items[i : i + EXTRACT_BATCH_SIZE]
        results = _extract_definitions_batch(chunk, cancel_check=cancel_check, domain_hint=domain_hint)
        for (concept, _), defn in zip(chunk, results):
            if concept in processed_concepts:
                continue
            if defn:
                concept_definitions[concept] = defn
                report.definitions_added[concept] = defn
                processed_concepts.add(concept)

    # Second pass: concepts that failed, try next page
    for concept in gaps:
        if concept in processed_concepts:
            continue
        for page in concept_to_pages.get(concept, [])[1:]:
            if cancel_check and cancel_check():
                break
            if not page.content or len(page.content.strip()) < 50:
                continue
            results = _extract_definitions_batch([(concept, page)], cancel_check=cancel_check, domain_hint=domain_hint)
            if results and results[0]:
                concept_definitions[concept] = results[0]
                report.definitions_added[concept] = results[0]
                processed_concepts.add(concept)
                break

    # Batch graph updates: use _loading_mode to skip per-node embedding, then batch embed
    if not concept_definitions:
        logger.warning("[GapRepair] No definitions extracted: batch_items=%d, pages=%d",
                       len(batch_items), len(pages))
        return report

    g = graph.get_graph()
    to_update: list[tuple[str, str, str, str]] = []
    for concept, defn in concept_definitions.items():
        if concept not in g:
            continue
        data = dict(g.nodes[concept])
        to_update.append((concept, data.get("type", "Class"), data.get("kind", "class"), defn))

    if not to_update:
        return report

    _progress("gap_repair_apply", f"Applying {len(to_update)} definitions", {"count": len(to_update)})

    try:
        graph._loading_mode = True
        for concept, etype, kind, defn in to_update:
            graph.add_entity(
                concept,
                etype,
                kind=kind,
                description=defn,
                source_document="web_gap_repair",
                provenance={"origin": "repair", "source": "web", "type": "definition"},
            )
            report.gaps_repaired += 1
    finally:
        graph._loading_mode = False

    # Batch embed updated nodes
    if to_update:
        try:
            model = get_embedding_model()
            dim = get_embedding_dimension()
            texts = [f"{c} {d}" for c, _, _, d in to_update]
            for j in range(0, len(texts), 64):
                batch = texts[j : j + 64]
                embs = model.encode(batch, normalize_embeddings=True)
                for k, (concept, _, _, _) in enumerate(to_update[j : j + 64]):
                    if k < embs.shape[0]:
                        graph.embedding_cache[concept] = embs[k]
            logger.info("[GapRepair] Batch embedded %d updated nodes", len(to_update))
        except Exception as e:
            logger.warning("[GapRepair] Batch embed failed, cache may be stale: %s", e)

    for concept in concept_definitions:
        logger.info("[GapRepair] Added definition for %r", concept)

    return report
