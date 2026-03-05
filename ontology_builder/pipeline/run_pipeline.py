"""Orchestrate the living ontology pipeline: load, chunk, extract, merge, optional inference."""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from ontology_builder.pipeline.chunker import chunk_text
from ontology_builder.pipeline.loader import load_document
from ontology_builder.pipeline.extractor import extract_ontology
from ontology_builder.pipeline.ontology_builder import update_graph
from ontology_builder.pipeline.relation_inferer import infer_relations
from ontology_builder.storage.graphdb import OntologyGraph
from app.config import get_settings

logger = logging.getLogger(__name__)


def process_document(path: str, run_inference: bool = True, verbose: bool = True) -> OntologyGraph:
    """Load document, chunk, extract, merge, optionally infer relations.

    Args:
        path: File path to PDF, DOCX, TXT, or MD.
        run_inference: If True, run LLM relation inference after extraction.
        verbose: If True, show tqdm progress bars for extraction and merge stages.

    Returns:
        OntologyGraph with entities and relations.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If format is unsupported.
    """
    logger.info("[Pipeline] Starting | path=%s | run_inference=%s", path, run_inference)

    logger.info("[Pipeline] Step 1/5: Loading document")
    text = load_document(path)
    logger.info("[Pipeline] Document loaded | text_length=%d chars", len(text))

    logger.info("[Pipeline] Step 2/5: Chunking text")
    chunks = chunk_text(text)
    logger.info("[Pipeline] Chunking complete | chunks=%d", len(chunks))

    settings = get_settings()
    logger.info("[Pipeline] Step 3/5: Extracting entities and relations per chunk (LLM) | workers=%d", settings.llm_parallel_workers)
    graph = OntologyGraph()
    chunk_iter = tqdm(
        chunks,
        desc="Extracting chunks",
        disable=not verbose,
        unit="chunk",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    )
    with ThreadPoolExecutor(max_workers=settings.llm_parallel_workers) as executor:
        extractions = list(executor.map(extract_ontology, chunk_iter))
    for extraction in extractions:
        update_graph(graph, extraction, verbose=verbose)

    logger.info("[Pipeline] Step 4/5: Merging complete | nodes=%d | edges=%d",
                graph.get_graph().number_of_nodes(), graph.get_graph().number_of_edges())

    if run_inference:
        logger.info("[Pipeline] Step 5/5: Running LLM relation inference")
        inferred = infer_relations(graph)
        if inferred:
            logger.info("[Pipeline] Inferred %d additional relations", len(inferred))
            update_graph(graph, {"entities": [], "relations": inferred}, verbose=verbose)
        else:
            logger.debug("[Pipeline] No relations inferred above threshold")
    else:
        logger.info("[Pipeline] Step 5/5: Skipping inference (run_inference=False)")

    logger.info("[Pipeline] Complete | nodes=%d | edges=%d",
                graph.get_graph().number_of_nodes(), graph.get_graph().number_of_edges())
    return graph
