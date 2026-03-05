"""Orchestrate the living ontology pipeline: load, chunk, extract, merge, taxonomy, inference.

Supports both legacy (single-shot) and sequential (Bakker Approach B) extraction modes.
Produces a PipelineReport for reproducibility and evaluation.
"""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from app.config import get_settings
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
) -> tuple[OntologyGraph, PipelineReport]:
    """Load document, chunk, extract, merge, build taxonomy, reason.

    Args:
        path: File path to PDF, DOCX, TXT, or MD.
        run_inference: If True, run LLM relation inference after extraction.
        verbose: If True, show tqdm progress bars.
        sequential: If True, use 3-stage sequential extraction (Bakker B).
        run_reasoning: If True, run OWL 2 RL reasoning after extraction.

    Returns:
        Tuple of (OntologyGraph, PipelineReport).
    """
    report = PipelineReport(document_path=path, extraction_mode="sequential" if sequential else "legacy")

    with PipelineTimer() as timer:
        logger.info("[Pipeline] Starting | path=%s | mode=%s", path, report.extraction_mode)

        # Step 1: Load
        logger.info("[Pipeline] Step 1/6: Loading document")
        text = load_document(path)
        logger.info("[Pipeline] Document loaded | text_length=%d chars", len(text))

        # Step 2: Chunk
        logger.info("[Pipeline] Step 2/6: Chunking text")
        chunks = chunk_text(text)
        report.total_chunks = len(chunks)
        logger.info("[Pipeline] Chunking complete | chunks=%d", len(chunks))

        # Step 3: Extract
        settings = get_settings()
        graph = OntologyGraph()

        if sequential:
            _extract_sequential(chunks, graph, text, path, report, settings, verbose)
        else:
            _extract_legacy(chunks, graph, report, settings, verbose)

        logger.info(
            "[Pipeline] Step 4/6: Merge complete | nodes=%d edges=%d",
            graph.get_graph().number_of_nodes(),
            graph.get_graph().number_of_edges(),
        )

        # Record extraction totals (before LLM inference)
        report.extraction_classes = len(graph.get_classes())
        report.extraction_instances = len(graph.get_instances())
        report.extraction_relations = graph.get_graph().number_of_edges()
        report.extraction_axioms = len(graph.axioms)

        # Step 5: LLM relation inference (optional)
        if run_inference:
            logger.info("[Pipeline] Step 5/6: Running LLM relation inference")
            inferred = infer_relations(graph)
            if inferred:
                report.llm_inferred_relations = len(inferred)
                logger.info("[Pipeline] Inferred %d additional relations", len(inferred))
                update_graph(graph, {"entities": [], "relations": inferred}, verbose=verbose)
            else:
                logger.debug("[Pipeline] No relations inferred above threshold")
        else:
            logger.info("[Pipeline] Step 5/6: Skipping LLM inference")

        # Step 6: OWL 2 RL reasoning (optional)
        if run_reasoning:
            logger.info("[Pipeline] Step 6/6: Running OWL 2 RL reasoning")
            reasoning_result = run_owl_inference(graph)
            report.reasoning_inferred_edges = reasoning_result.inferred_edges
            report.reasoning_iterations = reasoning_result.iterations
            report.consistency_violations = reasoning_result.consistency_violations
        else:
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
    settings: object,
    verbose: bool,
) -> None:
    """3-stage sequential extraction with taxonomy building."""
    logger.info("[Pipeline] Step 3/6: Sequential extraction | chunks=%d", len(chunks))

    all_extractions: list[OntologyExtraction] = []
    chunk_iter = tqdm(
        enumerate(chunks),
        total=len(chunks),
        desc="Extracting chunks (sequential)",
        disable=not verbose,
        unit="chunk",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    )
    for idx, chunk in chunk_iter:
        extraction = extract_ontology_sequential(chunk, source_document=doc_path)
        all_extractions.append(extraction)
        report.chunk_stats.append(ChunkStats(
            chunk_index=idx,
            chunk_length=len(chunk),
            classes_extracted=len(extraction.classes),
            instances_extracted=len(extraction.instances),
            relations_extracted=len(extraction.object_properties),
            axioms_extracted=len(extraction.axioms),
        ))

    all_classes = []
    for ext in all_extractions:
        all_classes.extend(ext.classes)
    if all_classes:
        logger.info("[Pipeline] Building taxonomy from %d classes", len(all_classes))
        taxonomy_classes = build_taxonomy(all_classes, full_text)
        class_parent_map = {c.name: c.parent for c in taxonomy_classes}
    else:
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
    settings: object,
    verbose: bool,
) -> None:
    """Legacy single-shot extraction."""
    logger.info("[Pipeline] Step 3/6: Legacy extraction | chunks=%d", len(chunks))
    workers = getattr(settings, "llm_parallel_workers", 4)
    chunk_iter = tqdm(
        chunks,
        desc="Extracting chunks",
        disable=not verbose,
        unit="chunk",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        extractions = list(executor.map(extract_ontology, chunk_iter))
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
