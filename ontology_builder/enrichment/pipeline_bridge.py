"""
Bridge between the enrichment module and the existing ontology pipeline.

Key design decisions
--------------------
- We call process_document() on the temp .md file to get a fresh OntologyGraph.
- We run analysis (graph health, structural quality) on the enrichment graph.
- We only MERGE if threshold is met (min nodes and/or min quality score).
- Embedding cache from the enrichment sub-graph is merged into the main cache.
- If kb_path is provided, we call save_to_path_with_metadata() to persist.

We deliberately do NOT reload the full graph from disk — this avoids the
~1169 redundant encode calls identified in docs/technical/GRAPH_LOAD_STORE_SAVE_RUNDOWN.md.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import orjson

logger = logging.getLogger(__name__)

# Thresholds for merging enrichment into main graph
DEFAULT_MIN_NODES_TO_MERGE = 1
DEFAULT_MIN_QUALITY_SCORE = 0.0  # 0 = accept any; 0.2+ filters low-quality


@dataclass
class PipelineBridgeReport:
    nodes_added    : int = 0
    nodes_updated  : int = 0  # existing nodes enriched with descriptions/synonyms
    edges_added    : int = 0
    axioms_added   : int = 0
    dp_added       : int = 0
    errors         : list = field(default_factory=list)
    analysis       : dict = field(default_factory=dict)  # health, structural, reliability
    merge_skipped  : bool = False
    skip_reason    : str = ""


def ingest_document(
    doc_path: Path,
    graph,
    kb_path=None,
    verbose=True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    min_nodes_to_merge: int = DEFAULT_MIN_NODES_TO_MERGE,
    min_quality_score: float = DEFAULT_MIN_QUALITY_SCORE,
) -> PipelineBridgeReport:
    """
    Process doc_path through the existing pipeline, analyze the enrichment graph,
    then merge into the live graph only if threshold is met.

    Args:
        doc_path : Path — the .md file produced by doc_builder
        graph    : OntologyGraph — live in-memory graph (mutated in-place)
        kb_path  : Path | None — if given, save graph after merge
        verbose  : bool
        progress_callback : optional (step, data) for UI progress
        min_nodes_to_merge : skip merge if enrichment graph has fewer nodes
        min_quality_score  : skip merge if reliability score below this (0–1)

    Returns:
        PipelineBridgeReport
    """
    from ontology_builder.pipeline.run_pipeline import process_document
    from ontology_builder.storage import graph_store
    from ontology_builder.quality.structural_scorer import (
        compute_structural_metrics,
        compute_reliability_score,
    )
    from ontology_builder.evaluation.graph_health import compute_graph_health

    def _progress(step: str, data: dict):
        if progress_callback:
            progress_callback(step, data)

    report = PipelineBridgeReport()

    # --- run pipeline on enrichment doc ---
    logger.info("[Bridge] Processing enrichment doc: %s", doc_path)
    _progress("web_pipeline_run", {"message": "Running extraction pipeline", "doc_path": str(doc_path)})
    try:
        enrich_graph, _pipeline_report = process_document(
            str(doc_path),
            verbose=verbose,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
    except Exception as e:
        report.errors.append(f"process_document failed: {e}")
        logger.error(f"[Bridge] {e}")
        return report

    nx_src = enrich_graph.get_graph()
    num_nodes = nx_src.number_of_nodes()
    num_edges = nx_src.number_of_edges()

    # --- analyze enrichment graph (existing stack) ---
    _progress("web_analysis_start", {"message": "Analyzing enrichment graph"})
    try:
        health = compute_graph_health(enrich_graph)
        metrics = compute_structural_metrics(enrich_graph)
        reliability = compute_reliability_score(metrics)
        report.analysis = {
            "health": health,
            "structural": {
                "num_classes": metrics.num_classes,
                "num_instances": metrics.num_instances,
                "depth_variance": metrics.depth_variance,
                "instance_ratio": metrics.instance_to_class_ratio,
            },
            "reliability": {
                "score": reliability.score,
                "grade": reliability.grade,
                "reasons": reliability.reasons[:5],
            },
        }
        _progress("web_analysis_done", {
            "nodes": num_nodes,
            "edges": num_edges,
            "grade": reliability.grade,
            "score": reliability.score,
        })
    except Exception as e:
        logger.warning(f"[Bridge] Analysis failed: {e}")
        report.analysis = {"error": str(e)}
        _progress("web_analysis_done", {"nodes": num_nodes, "edges": num_edges, "error": str(e)})

    # --- threshold check ---
    quality_ok = report.analysis.get("reliability", {}).get("score", 0) >= min_quality_score
    nodes_ok = num_nodes >= min_nodes_to_merge
    if not nodes_ok:
        report.merge_skipped = True
        report.skip_reason = f"Enrichment graph has {num_nodes} nodes (min {min_nodes_to_merge})"
        _progress("web_threshold_check", {"passed": False, "reason": report.skip_reason})
        if verbose:
            logger.info(f"[Bridge] Skipped merge: {report.skip_reason}")
        return report
    if not quality_ok:
        report.merge_skipped = True
        score = report.analysis.get("reliability", {}).get("score", 0)
        report.skip_reason = f"Quality score {score:.2f} below threshold {min_quality_score}"
        _progress("web_threshold_check", {"passed": False, "reason": report.skip_reason})
        if verbose:
            logger.info(f"[Bridge] Skipped merge: {report.skip_reason}")
        return report

    _progress("web_threshold_check", {"passed": True, "message": "Threshold met, merging"})

    nx_dst = graph.get_graph()
    existing_nodes = set(nx_dst.nodes())
    existing_edges = {(u, v, d.get("relation")) for u, v, d in nx_dst.edges(data=True)}

    # --- merge nodes (add new, update existing with richer descriptions) ---
    for node, data in nx_src.nodes(data=True):
        try:
            graph.add_entity(
                node,
                data.get("type", "Class"),
                kind        = data.get("kind", "class"),
                description = data.get("description", ""),
                synonyms    = data.get("synonyms", []),
                source_documents = data.get("source_documents", [str(doc_path)]),
            )
            if node not in existing_nodes:
                report.nodes_added += 1
            elif (data.get("description") or data.get("synonyms")):
                report.nodes_updated += 1
        except Exception as e:
            report.errors.append(f"add_entity({node}): {e}")

    # --- merge edges (batch) ---
    relations_to_add = []
    for u, v, data in nx_src.edges(data=True):
        rel = data.get("relation", "related_to")
        if (u, v, rel) not in existing_edges:
            src_docs = data.get("source_documents", [str(doc_path)])
            relations_to_add.append({
                "source"          : u,
                "target"          : v,
                "relation"        : rel,
                "confidence"      : data.get("confidence", 0.7),
                "source_document" : src_docs[0] if src_docs else str(doc_path),
            })

    if relations_to_add:
        try:
            graph.add_relations_batch(relations_to_add)
            report.edges_added = len(relations_to_add)
        except Exception as e:
            report.errors.append(f"add_relations_batch: {e}")

    # --- merge axioms ---
    existing_axioms = {a.get("description", "") for a in graph._axioms}
    for axiom in enrich_graph._axioms:
        if axiom.get("description", "") not in existing_axioms:
            try:
                graph.add_axiom(axiom)
                report.axioms_added += 1
            except Exception as e:
                report.errors.append(f"add_axiom: {e}")

    # --- merge data properties ---
    existing_dp = {
        (dp.get("entity"), dp.get("attribute"), dp.get("value"))
        for dp in graph._data_properties
    }
    for dp in enrich_graph._data_properties:
        key = (dp.get("entity"), dp.get("attribute"), dp.get("value"))
        if key not in existing_dp:
            try:
                graph.add_data_property(**dp)
                report.dp_added += 1
            except Exception as e:
                report.errors.append(f"add_data_property: {e}")

    # --- merge embedding cache (avoid re-encoding on next QA build) ---
    if hasattr(enrich_graph, "embedding_cache") and enrich_graph.embedding_cache:
        if not hasattr(graph, "embedding_cache") or graph.embedding_cache is None:
            graph.embedding_cache = {}
        for k, v in enrich_graph.embedding_cache.items():
            if k not in graph.embedding_cache:
                graph.embedding_cache[k] = v

    if verbose:
        logger.info(
            f"[Bridge] Merged: +{report.nodes_added} nodes, {report.nodes_updated} updated, "
            f"+{report.edges_added} edges, "
            f"+{report.axioms_added} axioms, "
            f"+{report.dp_added} data properties"
        )

    # --- optional persist ---
    if kb_path is not None:
        try:
            # Refresh store export (graph was mutated in-place)
            graph_store.set_graph(graph)
            kb_id = kb_path.stem
            meta_path = kb_path.with_suffix(".meta.json")
            name = kb_id
            description = ""
            if meta_path.exists():
                try:
                    meta = orjson.loads(meta_path.read_bytes())
                    name = meta.get("name", kb_id)
                    description = meta.get("description", "")
                except (orjson.JSONDecodeError, OSError):
                    pass
            graph_store.save_to_path_with_metadata(
                kb_path,
                name=name,
                kb_id=kb_id,
                description=description,
                documents=[str(doc_path)],
                merge_documents=True,
            )
            if verbose:
                logger.info(f"[Bridge] Saved to {kb_path}")
        except Exception as e:
            report.errors.append(f"save: {e}")

    return report
