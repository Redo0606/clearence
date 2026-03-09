# ontology_builder/enrichment/__init__.py

import logging

from ontology_builder.pipeline.run_pipeline import PipelineCancelledError

from .query_planner import plan_queries
from .web_fetcher import fetch_and_score, WebPage
from .doc_builder import build_document
from .pipeline_bridge import ingest_document, PipelineBridgeReport

logger = logging.getLogger(__name__)


class EnrichmentReport:
    def __init__(self, queries, pages_fetched, doc_path, pipeline_report):
        self.queries         = queries
        self.pages_fetched   = pages_fetched
        self.doc_path        = doc_path
        self.pipeline_report = pipeline_report

    def __repr__(self):
        return (f"EnrichmentReport(queries={len(self.queries)}, "
                f"pages={self.pages_fetched}, doc={self.doc_path})")


def enrich_graph(graph, kb_path=None, max_queries=None, min_fidelity=0.3, verbose=True,
                 progress_callback=None, use_llm_queries=True,
                 use_llm_content_score=True,
                 min_nodes_to_merge=1, min_quality_score=0.0,
                 cancel_check=None,
                 ontology_language=None):
    """
    Enrich an OntologyGraph with web-sourced information.

    Args:
        graph        : OntologyGraph — the live in-memory graph (not reloaded)
        kb_path      : Path | None   — if provided, save updated graph after ingestion
        max_queries  : int | None    — override auto-computed query cap
        min_fidelity : float         — drop results below this score (0–1)
        verbose      : bool
        progress_callback : callable(step, data) | None — optional progress callback
        use_llm_queries    : bool — batch-infer queries via LLM (default True)
        use_llm_content_score : bool — batch-score pages via LLM for objective relevance+quality (default True)
        cancel_check      : callable() -> bool | None — if returns True, abort enrichment
        min_nodes_to_merge: int — skip merge if enrichment has fewer nodes
        min_quality_score : float — skip merge if reliability score below this
        ontology_language : str | None — ISO 639-1. Queries and extracted content in this language. From KB meta if omitted.

    Returns:
        EnrichmentReport(queries, pages_fetched, doc_path, pipeline_report)
    """
    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    _progress("web_queries_start", {"message": "Inferring search queries from graph"})
    if cancel_check and cancel_check():
        raise PipelineCancelledError("Enrichment cancelled")
    queries = plan_queries(
        graph,
        max_queries=max_queries,
        use_llm=use_llm_queries,
        kb_path=kb_path,
        ontology_language=ontology_language,
    )
    _progress("web_queries_planned", {"queries": queries, "count": len(queries)})
    logger.info("[Enrichment] Starting fetch: %d queries", len(queries))
    if cancel_check and cancel_check():
        raise PipelineCancelledError("Enrichment cancelled")
    pages = fetch_and_score(
        queries,
        min_fidelity=min_fidelity,
        use_llm_content_score=use_llm_content_score,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    _progress("web_pages_fetched", {"count": len(pages)})
    logger.info("[Enrichment] Fetched %d pages", len(pages))

    if not pages:
        _progress("web_document_built", {"doc_path": "", "skipped": True})
        _progress("web_pipeline_run", {"skipped": True, "reason": "No pages to build document"})
        _progress("web_analysis_start", {"skipped": True})
        _progress("web_analysis_done", {"nodes": 0, "edges": 0, "skipped": True})
        _progress("web_threshold_check", {"passed": False, "reason": "No content fetched — try lowering min fidelity"})
        _progress("web_merge_done", {
            "nodes_added": 0, "nodes_updated": 0, "edges_added": 0, "axioms_added": 0, "dp_added": 0,
            "merge_skipped": True, "skip_reason": "No pages fetched", "analysis": {},
        })
        return EnrichmentReport(queries=queries, pages_fetched=0, doc_path=None, pipeline_report=PipelineBridgeReport(merge_skipped=True, skip_reason="No pages fetched"))

    if cancel_check and cancel_check():
        raise PipelineCancelledError("Enrichment cancelled")
    doc_path = build_document(pages, progress_callback=progress_callback, cancel_check=cancel_check)
    _progress("web_document_built", {"doc_path": str(doc_path)})
    logger.info("[Enrichment] Built document: %s", doc_path)
    if cancel_check and cancel_check():
        raise PipelineCancelledError("Enrichment cancelled")
    report = ingest_document(
        doc_path,
        graph,
        kb_path=kb_path,
        verbose=verbose,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        min_nodes_to_merge=min_nodes_to_merge,
        min_quality_score=min_quality_score,
        ontology_language=ontology_language,
    )
    _progress("web_merge_done", {
        "nodes_added": report.nodes_added,
        "nodes_updated": report.nodes_updated,
        "edges_added": report.edges_added,
        "axioms_added": report.axioms_added,
        "dp_added": report.dp_added,
        "merge_skipped": report.merge_skipped,
        "skip_reason": report.skip_reason,
        "analysis": report.analysis,
    })
    return EnrichmentReport(queries=queries, pages_fetched=len(pages),
                            doc_path=doc_path, pipeline_report=report)
