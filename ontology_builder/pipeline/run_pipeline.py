"""Orchestrate the living ontology pipeline: load, chunk, extract, merge, taxonomy, inference.

Supports both legacy (single-shot) and sequential (Bakker Approach B) extraction modes.
Produces a PipelineReport for reproducibility and evaluation.
"""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from tqdm import tqdm


class PipelineCancelledError(Exception):
    """Raised when the pipeline is cancelled (e.g. client disconnected)."""

from app.config import Settings, get_settings
from ontology_builder.evaluation.metrics import ChunkStats, PipelineReport, PipelineTimer
from ontology_builder.ontology.schema import OntologyExtraction
from ontology_builder.pipeline.chunker import chunk_text
from ontology_builder.pipeline.extractor import extract_ontology, extract_ontology_sequential
from ontology_builder.pipeline.loader import load_document
from ontology_builder.pipeline.ontology_builder import update_graph
from ontology_builder.pipeline.relation_inferer import infer_relations
from ontology_builder.pipeline.taxonomy_builder import build_taxonomy
from ontology_builder.reasoning.engine import run_inference as run_owl_inference
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def process_document(
    path: str,
    run_inference: bool = True,
    verbose: bool = True,
    sequential: bool = True,
    run_reasoning: bool = True,
    parallel_extraction: bool = True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[OntologyGraph, PipelineReport]:
    """Load document, chunk, extract, merge, build taxonomy, reason.

    Args:
        path: File path to PDF, DOCX, TXT, or MD.
        run_inference: If True, run LLM relation inference after extraction.
        verbose: If True, show tqdm progress bars.
        sequential: If True, use 3-stage sequential extraction (Bakker B).
        run_reasoning: If True, run OWL 2 RL reasoning after extraction.
        parallel_extraction: If True, process chunks in parallel (4 workers); if False, sequentially.
        progress_callback: Optional callback(step, data) for real-time progress.
        cancel_check: Optional callable returning True if pipeline should stop.

    Returns:
        Tuple of (OntologyGraph, PipelineReport).

    Raises:
        PipelineCancelledError: If cancel_check returns True.
    """
    def _check_cancel() -> None:
        if cancel_check and cancel_check():
            raise PipelineCancelledError("Pipeline cancelled by client")

    def _progress(step: str, data: dict | None = None) -> None:
        if progress_callback:
            progress_callback(step, data or {})

    mode = "parallel" if parallel_extraction else "sequential"
    if not sequential:
        mode = "legacy"
    report = PipelineReport(document_path=path, extraction_mode=mode)

    with PipelineTimer() as timer:
        logger.info("[Pipeline] Starting | path=%s | mode=%s", path, report.extraction_mode)
        _check_cancel()

        # Step 1: Load
        _progress("load", {"message": "Loading document"})
        logger.info("[Pipeline] Step 1/6: Loading document")
        text = load_document(path)
        logger.info("[Pipeline] Document loaded | text_length=%d chars", len(text))
        _progress("load_done", {"chars": len(text)})
        _check_cancel()

        # Step 2: Chunk
        _progress("chunk", {"message": "Chunking text"})
        logger.info("[Pipeline] Step 2/6: Chunking text")
        settings = get_settings()
        chunks = chunk_text(text, size=settings.chunk_size, overlap=settings.chunk_overlap)
        report.total_chunks = len(chunks)
        logger.info("[Pipeline] Chunking complete | chunks=%d", len(chunks))
        _progress("chunk_done", {"total_chunks": len(chunks)})
        _check_cancel()

        # Step 3: Extract
        graph = OntologyGraph()

        if sequential:
            _extract_sequential(chunks, graph, text, path, report, settings, verbose, parallel_extraction, _progress, _check_cancel)
        else:
            _extract_legacy(chunks, graph, report, settings, verbose, parallel_extraction, _progress, _check_cancel)

        logger.info(
            "[Pipeline] Step 4/6: Merge complete | nodes=%d edges=%d",
            graph.get_graph().number_of_nodes(),
            graph.get_graph().number_of_edges(),
        )
        edge_count = graph.get_graph().number_of_edges()
        _progress("merge_done", {
            "classes": len(graph.get_classes()),
            "instances": len(graph.get_instances()),
            "relations": edge_count,
            "axioms": len(graph.axioms),
        })
        _check_cancel()

        # Record extraction totals (before LLM inference)
        report.extraction_classes = len(graph.get_classes())
        report.extraction_instances = len(graph.get_instances())
        report.extraction_relations = graph.get_graph().number_of_edges()
        report.extraction_axioms = len(graph.axioms)

        # Step 5: LLM relation inference (optional)
        if run_inference:
            _check_cancel()
            _progress("inference", {"message": "Running LLM relation inference"})
            logger.info("[Pipeline] Step 5/6: Running LLM relation inference")
            inferred = infer_relations(graph)
            if inferred:
                report.llm_inferred_relations = len(inferred)
                logger.info("[Pipeline] Inferred %d additional relations", len(inferred))
                update_graph(graph, {"entities": [], "relations": inferred}, verbose=verbose)
            else:
                logger.debug("[Pipeline] No relations inferred above threshold")
            _progress("inference_done", {"inferred": report.llm_inferred_relations})
        else:
            _progress("inference_skip", {})
            logger.info("[Pipeline] Step 5/6: Skipping LLM inference")

        # Step 6: OWL 2 RL reasoning (optional)
        if run_reasoning:
            _check_cancel()
            _progress("reasoning", {"message": "Running OWL 2 RL reasoning"})
            logger.info("[Pipeline] Step 6/6: Running OWL 2 RL reasoning")
            reasoning_result = run_owl_inference(graph)
            report.reasoning_inferred_edges = reasoning_result.inferred_edges
            report.reasoning_iterations = reasoning_result.iterations
            report.consistency_violations = reasoning_result.consistency_violations
            _progress("reasoning_done", {
                "inferred_edges": reasoning_result.inferred_edges,
                "iterations": reasoning_result.iterations,
            })
        else:
            _progress("reasoning_skip", {})
            logger.info("[Pipeline] Step 6/6: Skipping reasoning")

        # Tally totals
        report.total_classes = len(graph.get_classes())
        report.total_instances = len(graph.get_instances())
        report.total_relations = graph.get_graph().number_of_edges()
        report.total_axioms = len(graph.axioms)
        report.total_data_properties = len(graph.data_properties)

    report.elapsed_seconds = timer.elapsed
    logger.info(
        "[Pipeline] Complete | nodes=%d edges=%d | %.1fs",
        graph.get_graph().number_of_nodes(),
        graph.get_graph().number_of_edges(),
        timer.elapsed,
    )
    return graph, report


def _extract_sequential(
    chunks: list[str],
    graph: OntologyGraph,
    full_text: str,
    doc_path: str,
    report: PipelineReport,
    settings: Settings,
    verbose: bool,
    parallel: bool = True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> None:
    """3-stage sequential extraction (Bakker B). Chunks processed in parallel or sequentially."""
    workers = settings.get_llm_parallel_workers()
    total = len(chunks)
    mode_label = "parallel" if parallel else "sequential"
    logger.info("[Pipeline] Step 3/6: Extraction | chunks=%d | mode=%s | workers=%d", len(chunks), mode_label, workers if parallel else 1)

    def _extract_chunk(chunk_data: tuple[int, str]) -> tuple[int, OntologyExtraction]:
        idx, chunk = chunk_data
        if cancel_check:
            cancel_check()
        if (idx + 1) % 5 == 0 or idx == 0:
            logger.info("[Pipeline] Step 3/6: Extracting | chunk %d/%d", idx + 1, total)
        extraction = extract_ontology_sequential(chunk, source_document=doc_path)
        if progress_callback:
            progress_callback("extract", {
                "current": idx + 1,
                "total": total,
                "chunk_index": idx,
                "message": f"Extracted chunk {idx + 1}/{total}",
                "classes": len(extraction.classes),
                "instances": len(extraction.instances),
                "relations": len(extraction.object_properties),
                "axioms": len(extraction.axioms),
            })
        return idx, extraction

    chunk_iter = tqdm(
        list(enumerate(chunks)),
        total=total,
        desc=f"Extracting chunks ({mode_label})",
        disable=not verbose,
        unit="chunk",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    )

    if parallel:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_extract_chunk, chunk_iter))
    else:
        results = [_extract_chunk(item) for item in chunk_iter]

    all_extractions = [ext for _, ext in sorted(results, key=lambda x: x[0])]
    logger.info("[Pipeline] Step 3/6: Extraction complete | chunks=%d", len(all_extractions))
    for idx, extraction in enumerate(all_extractions):
        report.chunk_stats.append(ChunkStats(
            chunk_index=idx,
            chunk_length=len(chunks[idx]),
            classes_extracted=len(extraction.classes),
            instances_extracted=len(extraction.instances),
            relations_extracted=len(extraction.object_properties),
            axioms_extracted=len(extraction.axioms),
        ))

    all_classes = []
    for ext in all_extractions:
        all_classes.extend(ext.classes)
    if all_classes:
        if progress_callback:
            progress_callback("taxonomy", {"message": "Building taxonomy", "classes": len(all_classes)})
        logger.info("[Pipeline] Building taxonomy from %d classes", len(all_classes))
        taxonomy_classes = build_taxonomy(all_classes, full_text)
        if progress_callback:
            progress_callback("taxonomy_done", {"classes": len(taxonomy_classes)})
        class_parent_map = {c.name: c.parent for c in taxonomy_classes}
    else:
        if progress_callback:
            progress_callback("taxonomy_skip", {})
        class_parent_map = {}

    for ext in all_extractions:
        for cls in ext.classes:
            if cls.name in class_parent_map:
                cls.parent = class_parent_map[cls.name]
        update_graph(graph, ext, verbose=False)


def _extract_legacy(
    chunks: list[str],
    graph: OntologyGraph,
    report: PipelineReport,
    settings: Settings,
    verbose: bool,
    parallel: bool = True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> None:
    """Legacy single-shot extraction."""
    total = len(chunks)
    workers = settings.get_llm_parallel_workers()
    mode_label = "parallel" if parallel else "sequential"
    logger.info("[Pipeline] Step 3/6: Legacy extraction | chunks=%d | mode=%s", len(chunks), mode_label)

    def _extract_with_progress(chunk_data: tuple[int, str]) -> dict:
        idx, chunk = chunk_data
        if cancel_check:
            cancel_check()
        if (idx + 1) % 5 == 0 or idx == 0:
            logger.info("[Pipeline] Step 3/6: Extracting | chunk %d/%d", idx + 1, total)
        result = extract_ontology(chunk)
        entities = result.get("entities", [])
        relations = result.get("relations", [])
        if progress_callback:
            progress_callback("extract", {
                "current": idx + 1,
                "total": total,
                "chunk_index": idx,
                "message": f"Extracted chunk {idx + 1}/{total}",
                "classes": len(entities),
                "instances": 0,
                "relations": len(relations),
                "axioms": 0,
            })
        return result

    chunk_iter = tqdm(
        list(enumerate(chunks)),
        desc=f"Extracting chunks ({mode_label})",
        disable=not verbose,
        unit="chunk",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    )
    if parallel:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            extractions = list(executor.map(_extract_with_progress, chunk_iter))
    else:
        extractions = [_extract_with_progress(item) for item in chunk_iter]
    logger.info("[Pipeline] Step 3/6: Extraction complete | chunks=%d", len(extractions))
    for idx, extraction in enumerate(extractions):
        update_graph(graph, extraction, verbose=verbose)
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        report.chunk_stats.append(ChunkStats(
            chunk_index=idx,
            chunk_length=len(chunks[idx]),
            classes_extracted=len(entities),
            relations_extracted=len(relations),
        ))
