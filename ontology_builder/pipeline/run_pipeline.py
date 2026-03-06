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

from core.config import Settings, get_settings
from ontology_builder.evaluation.metrics import ChunkStats, PipelineReport, PipelineTimer
from ontology_builder.ontology.schema import OntologyExtraction
from ontology_builder.pipeline.chunker import chunk_text
from ontology_builder.pipeline.extractor import extract_ontology, extract_ontology_sequential
from ontology_builder.pipeline.loader import load_document
from ontology_builder.pipeline.ontology_builder import update_graph, update_graph_from_aggregated
from ontology_builder.pipeline.relation_inferer import infer_cross_component_relations, infer_relations
from ontology_builder.pipeline.taxonomy_builder import build_taxonomy
from ontology_builder.reasoning.engine import run_inference as run_owl_inference
from ontology_builder.quality import (
    OntologyQualityReport,
    check_relation_consistency,
    compute_reliability_score,
    compute_structural_metrics,
    enrich_hierarchy,
    boost_population,
    evaluate_relation_correctness,
)
from ontology_builder.ontology.canonicalizer import canonicalize_batch
from ontology_builder.repair import RepairConfig, repair_graph, repair_graph_incremental
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def _aggregate_extractions(
    all_extractions: list[OntologyExtraction],
    class_parent_map: dict[str, str | None],
    batch_size: int | None = None,
) -> dict:
    """Pre-aggregate triples and nodes across chunks in batches; batch canonicalize names.

    Returns dict with relations (vote_count, chunk_ids, confidence), classes, instances,
    data_properties, axioms. Names are canonicalized so same concept/entity merges.
    """
    settings = get_settings()
    agg_batch = batch_size or max(1, settings.aggregation_batch_size)

    # Collect unique names by kind for batch canonicalization
    class_names: list[str] = []
    instance_names: list[str] = []
    relation_endpoints: set[str] = set()
    for ext in all_extractions:
        for c in ext.classes:
            class_names.append(c.name)
        for i in ext.instances:
            instance_names.append(i.name)
        for op in ext.object_properties:
            relation_endpoints.add(op.source)
            relation_endpoints.add(op.target)
    class_names = list(dict.fromkeys(class_names))
    instance_names = list(dict.fromkeys(instance_names))
    relation_endpoints = relation_endpoints - set(class_names) - set(instance_names)
    other_names = list(relation_endpoints)

    name_to_canonical: dict[str, str] = {}
    if class_names:
        for name, can in zip(class_names, canonicalize_batch(class_names, kind="class")):
            name_to_canonical[name] = can
    if instance_names:
        for name, can in zip(instance_names, canonicalize_batch(instance_names, kind="instance")):
            name_to_canonical[name] = can
    if other_names:
        for name, can in zip(other_names, canonicalize_batch(other_names, kind="entity")):
            name_to_canonical[name] = can

    def _canon(s: str) -> str:
        return name_to_canonical.get(s, s)

    # Build triple map: (src_can, rel, tgt_can) -> [(chunk_id, confidence), ...]
    triple_to_occurrences: dict[tuple[str, str, str], list[tuple[int, float]]] = {}
    # Process extractions in batches for memory
    for start in range(0, len(all_extractions), agg_batch):
        batch = all_extractions[start : start + agg_batch]
        for chunk_id, ext in enumerate(batch):
            actual_chunk_id = start + chunk_id
            for op in ext.object_properties:
                src_can = _canon(op.source)
                tgt_can = _canon(op.target)
                key = (src_can, op.relation, tgt_can)
                triple_to_occurrences.setdefault(key, []).append((actual_chunk_id, float(op.confidence)))
            for cls in ext.classes:
                if cls.parent:
                    src_can = _canon(cls.name)
                    tgt_can = _canon(cls.parent)
                    key = (src_can, "subClassOf", tgt_can)
                    triple_to_occurrences.setdefault(key, []).append((actual_chunk_id, 1.0))

    relations = []
    for (src, rel, tgt), occs in triple_to_occurrences.items():
        chunk_ids = sorted(set(cid for cid, _ in occs))
        confs = [c for _, c in occs]
        avg_conf = sum(confs) / len(confs) if confs else 1.0
        relations.append({
            "source": src,
            "relation": rel,
            "target": tgt,
            "confidence": min(1.0, avg_conf),
            "vote_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
        })

    # Node maps: canonical name -> merged info
    class_map: dict[str, dict] = {}
    instance_map: dict[str, dict] = {}
    for chunk_id, ext in enumerate(all_extractions):
        for cls in ext.classes:
            can = _canon(cls.name)
            parent = class_parent_map.get(cls.name, cls.parent)
            parent_can = _canon(parent) if parent else None
            if can not in class_map:
                class_map[can] = {"chunk_ids": [], "descriptions": [], "parent": parent_can, "synonyms": []}
            class_map[can]["chunk_ids"].append(chunk_id)
            if (cls.description or "").strip():
                class_map[can]["descriptions"].append((cls.description or "").strip())
            if parent_can is not None:
                class_map[can]["parent"] = parent_can
            class_map[can]["synonyms"] = list(dict.fromkeys((class_map[can]["synonyms"] or []) + (cls.synonyms or [])))
        for inst in ext.instances:
            can = _canon(inst.name)
            class_can = _canon(inst.class_name)
            if can not in instance_map:
                instance_map[can] = {"chunk_ids": [], "class_name": class_can, "descriptions": []}
            instance_map[can]["chunk_ids"].append(chunk_id)
            if (inst.description or "").strip():
                instance_map[can]["descriptions"].append((inst.description or "").strip())
            instance_map[can]["class_name"] = class_can

    classes_out = []
    for name, info in class_map.items():
        chunk_ids = sorted(set(info["chunk_ids"]))
        desc = max(info["descriptions"], key=len) if info["descriptions"] else ""
        classes_out.append({
            "name": name,
            "description": desc,
            "parent": info.get("parent"),
            "synonyms": info.get("synonyms") or [],
            "chunk_ids": chunk_ids,
            "vote_count": len(chunk_ids),
        })
    instances_out = []
    for name, info in instance_map.items():
        chunk_ids = sorted(set(info["chunk_ids"]))
        desc = max(info["descriptions"], key=len) if info["descriptions"] else ""
        instances_out.append({
            "name": name,
            "class_name": info["class_name"],
            "description": desc,
            "chunk_ids": chunk_ids,
            "vote_count": len(chunk_ids),
        })

    # Data properties and axioms: merge from all (no vote aggregation)
    data_properties: list[dict] = []
    axioms: list[dict] = []
    for ext in all_extractions:
        for dp in ext.data_properties:
            data_properties.append({
                "entity": dp.entity,
                "attribute": dp.attribute,
                "value": dp.value,
                "datatype": dp.datatype,
            })
        for ax in ext.axioms:
            axioms.append(ax.model_dump() if hasattr(ax, "model_dump") else ax)

    return {
        "relations": relations,
        "classes": classes_out,
        "instances": instances_out,
        "data_properties": data_properties,
        "axioms": axioms,
    }


def process_document(
    path: str,
    run_inference: bool = True,
    verbose: bool = True,
    sequential: bool = True,
    run_reasoning: bool = True,
    run_repair: bool = True,
    parallel_extraction: bool = True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    ontology_language: str = "en",
) -> tuple[OntologyGraph, PipelineReport]:
    """Load document, chunk, extract, merge, build taxonomy, reason, optional repair.

    Args:
        path: File path to PDF, DOCX, TXT, or MD.
        run_inference: If True, run LLM relation inference after extraction.
        verbose: If True, show tqdm progress bars.
        sequential: If True, use 3-stage sequential extraction (Bakker B).
        run_reasoning: If True, run OWL 2 RL reasoning after extraction.
        run_repair: If True, run graph repair (root concept, orphans, bridge components) after reasoning.
        parallel_extraction: If True, process chunks in parallel (4 workers); if False, sequentially.
        progress_callback: Optional callback(step, data) for real-time progress.
        cancel_check: Optional callable returning True if pipeline should stop.
        ontology_language: ISO 639-1 language code (e.g. en, fr). All ontology elements are extracted in this language.

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
        chunks = chunk_text(
            text,
            size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            mode=getattr(settings, "chunk_mode", "semantic"),
        )
        report.total_chunks = len(chunks)
        logger.info("[Pipeline] Chunking complete | chunks=%d", len(chunks))
        _progress("chunk_done", {"total_chunks": len(chunks)})
        _check_cancel()

        # Step 3: Extract
        graph = OntologyGraph()

        if sequential:
            _extract_sequential(
                chunks, graph, text, path, report, settings, verbose, parallel_extraction,
                _progress, _check_cancel, ontology_language=ontology_language or "en",
            )
        else:
            _extract_legacy(
                chunks, graph, report, settings, verbose, parallel_extraction,
                _progress, _check_cancel, ontology_language=ontology_language or "en",
            )

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

        # Step 5: LLM relation inference (optional), with cross-component pass first
        if run_inference:
            _check_cancel()
            _progress("cross_component", {"message": "Inferring cross-component relations"})
            cross_rel = infer_cross_component_relations(graph, ontology_language=ontology_language or "en")
            if cross_rel:
                update_graph(graph, {"entities": [], "relations": cross_rel}, verbose=verbose)
                logger.info("[Pipeline] Cross-component relations added: %d", len(cross_rel))
            _progress("cross_component_done", {"inferred": len(cross_rel)})
            _check_cancel()
            _progress("inference", {"message": "Running LLM relation inference"})
            logger.info("[Pipeline] Step 5/6: Running LLM relation inference")
            inferred = infer_relations(graph, ontology_language=ontology_language or "en")
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

        # Step 7: Optional repair (root concept, orphans, bridge components)
        if run_repair:
            _check_cancel()
            _progress("repair", {"message": "Running graph repair"})
            logger.info("[Pipeline] Step 7/7: Running graph repair")
            def _repair_progress(phase: str, message: str, data: dict) -> None:
                if progress_callback:
                    progress_callback("repair", {"phase": phase, "message": message, **data})
            repair_report = repair_graph(
                graph,
                config=RepairConfig(),
                progress_callback=_repair_progress,
            )
            logger.info(
                "[Pipeline] Repair complete | edges_added=%d | orphans_linked=%d | components_bridged=%d",
                repair_report.edges_added,
                repair_report.orphans_linked,
                repair_report.components_bridged,
            )
            _progress("repair_done", {
                "edges_added": repair_report.edges_added,
                "orphans_linked": repair_report.orphans_linked,
                "components_bridged": repair_report.components_bridged,
            })
        else:
            _progress("repair_skip", {})
            logger.info("[Pipeline] Step 7/7: Skipping repair")

        # Tally totals
        report.total_classes = len(graph.get_classes())
        report.total_instances = len(graph.get_instances())
        report.total_relations = graph.get_graph().number_of_edges()
        report.total_axioms = len(graph.axioms)
        report.total_data_properties = len(graph.data_properties)

        # Plan 2: Quality metrics, consistency, enrichment, population booster, quality report
        _check_cancel()
        _progress("quality", {"message": "Computing structural quality"})
        repair_cfg = RepairConfig()
        metrics = compute_structural_metrics(graph)
        reliability = compute_reliability_score(metrics)
        relation_scores = evaluate_relation_correctness(graph)
        relation_scores.sort(key=lambda rs: rs.correctness_score, reverse=True)
        consistency = check_relation_consistency(graph)

        for crit in consistency.critical_conflicts:
            logger.error(
                "[Pipeline] Critical conflict: %s — %s ↔ %s | %s",
                crit.conflict_type, crit.entity_a, crit.entity_b, crit.suggested_resolution,
            )
        if repair_cfg.auto_resolve_critical and consistency.critical_conflicts:
            g = graph.get_graph()
            for crit in consistency.critical_conflicts:
                if crit.relation_a == "subClassOf" and g.has_edge(crit.entity_a, crit.entity_b):
                    g.remove_edge(crit.entity_a, crit.entity_b)
                    logger.info("[Pipeline] Auto-removed subClassOf(%s,%s)", crit.entity_a, crit.entity_b)
                elif crit.relation_b == "subClassOf" and g.has_edge(crit.entity_b, crit.entity_a):
                    g.remove_edge(crit.entity_b, crit.entity_a)
                    logger.info("[Pipeline] Auto-removed subClassOf(%s,%s)", crit.entity_b, crit.entity_a)
            consistency = check_relation_consistency(graph)

        if reliability.grade in ("D", "F"):
            logger.warning(
                "[Pipeline] Low reliability grade %s (%.2f) — consider re-running with taxonomy batch size or enrichment",
                reliability.grade, reliability.score,
            )
        if metrics.generic_relation_ratio >= 0.6:
            logger.warning(
                "[Pipeline] Over 60%% of edges use generic relation types. Enable repair_use_llm_relations=True and re-run.",
            )

        enrichment_added = 0
        if repair_cfg.enrich_hierarchy_if_low_quality and reliability.grade in ("C", "D", "F"):
            _progress("enrichment", {"message": "Hierarchy enrichment"})
            enrichment_added = enrich_hierarchy(graph, metrics, repair_cfg)
        boost_added = 0
        if repair_cfg.boost_population_if_sparse and metrics.instance_to_class_ratio < 0.5:
            _progress("population", {"message": "Population booster"})
            boost_added = boost_population(graph, text, repair_cfg)

        if enrichment_added or boost_added:
            metrics = compute_structural_metrics(graph)
            reliability = compute_reliability_score(metrics)

        recommended: list[str] = []
        if reliability.grade in ("D", "F"):
            recommended.append("Re-run taxonomy with larger batch size (Step 5 of Plan 1)")
        if metrics.depth_variance < 0.5:
            recommended.append("Enable hierarchy enrichment (Plan 2 Step P2-4)")
        if metrics.instance_to_class_ratio < 0.5:
            recommended.append("Enable population booster (Plan 2 Step P2-5)")
        if metrics.generic_relation_ratio >= 0.6:
            recommended.append("Enable repair_use_llm_relations=True (Plan 1 Step 8b)")
        if consistency.critical_conflicts:
            recommended.append("Review and resolve critical relation conflicts (Plan 2 Step P2-7)")

        warnings: list[str] = []
        if reliability.grade in ("D", "F"):
            warnings.append(f"Low reliability grade {reliability.grade}")
        if consistency.critical_conflicts:
            warnings.append(f"{len(consistency.critical_conflicts)} critical relation conflicts")

        report.quality = OntologyQualityReport(
            structural_metrics=metrics,
            reliability_score=reliability,
            relation_scores=relation_scores[:20],
            consistency_report=consistency,
            low_quality_warnings=warnings,
            recommended_actions=recommended,
        )
        _progress("quality_done", {"grade": reliability.grade, "score": reliability.score})

        logger.info(
            "[Pipeline] Quality | grade=%s score=%.2f depth_var=%.2f breadth_var=%.2f instance_ratio=%.2f named_rel=%.1f%%",
            reliability.grade, reliability.score,
            metrics.depth_variance, metrics.breadth_variance,
            metrics.instance_to_class_ratio, 100.0 * metrics.named_relation_ratio,
        )
        if recommended:
            logger.info("[Pipeline] Recommended actions: %s", recommended)
        # Print formatted quality summary to stdout
        _print_quality_summary(report.quality)

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
    ontology_language: str = "en",
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
        extraction = extract_ontology_sequential(
            chunk, source_document=doc_path, ontology_language=ontology_language
        )
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

    # Disable tqdm when streaming (progress_callback set) to avoid cluttering logs
    use_tqdm = verbose and not progress_callback
    chunk_iter = tqdm(
        list(enumerate(chunks)),
        total=total,
        desc=f"Extracting chunks ({mode_label})",
        disable=not use_tqdm,
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

    # Apply taxonomy parents then pre-aggregate (votes, chunk_ids, confidence) and update graph in batches
    for ext in all_extractions:
        for cls in ext.classes:
            if cls.name in class_parent_map:
                cls.parent = class_parent_map[cls.name]
    aggregated = _aggregate_extractions(all_extractions, class_parent_map)
    update_graph_from_aggregated(graph, aggregated, verbose=False)
    repair_config = RepairConfig()
    if getattr(repair_config, "repair_incremental", True):
        repair_graph_incremental(graph, config=repair_config)


def _extract_legacy(
    chunks: list[str],
    graph: OntologyGraph,
    report: PipelineReport,
    settings: Settings,
    verbose: bool,
    parallel: bool = True,
    progress_callback: Callable[[str, dict], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
    ontology_language: str = "en",
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
        result = extract_ontology(chunk, ontology_language=ontology_language)
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

    use_tqdm = verbose and not progress_callback
    chunk_iter = tqdm(
        list(enumerate(chunks)),
        desc=f"Extracting chunks ({mode_label})",
        disable=not use_tqdm,
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


def _print_quality_summary(quality: OntologyQualityReport) -> None:
    """Print formatted quality report to stdout (Plan 2 P2-8)."""
    if quality is None or quality.reliability_score is None or quality.structural_metrics is None:
        return
    m = quality.structural_metrics
    r = quality.reliability_score
    c = quality.consistency_report
    crit_count = len(c.critical_conflicts) if c else 0
    print("─────────────────────────────────────────")
    print(" ONTOLOGY QUALITY REPORT")
    print("─────────────────────────────────────────")
    print(f" Reliability Grade : {r.grade} ({r.score:.2f})")
    print(f" Depth Variance    : {m.depth_variance:.2f}  {'✓' if m.depth_variance >= 0.9 else '⚠' if m.depth_variance >= 0.5 else '✗'}")
    print(f" Breadth Variance  : {m.breadth_variance:.1f}  {'✓' if m.breadth_variance >= 20 else '⚠' if m.breadth_variance >= 5 else '✗'}")
    print(f" Instance Ratio    : {m.instance_to_class_ratio:.2f}  {'✓' if m.instance_to_class_ratio >= 1.0 else '⚠' if m.instance_to_class_ratio >= 0.3 else '✗'}")
    print(f" Named Relations   : {100 * m.named_relation_ratio:.0f}%   {'✓' if m.named_relation_ratio >= 0.3 else '⚠' if m.named_relation_ratio >= 0.15 else '✗'}")
    print(f" Critical Conflicts: {crit_count}     {'✓' if crit_count == 0 else '✗'}")
    print("─────────────────────────────────────────")
    if quality.recommended_actions:
        print(" Recommended Actions:")
        for action in quality.recommended_actions:
            print(f" → {action}")
    else:
        print(" No recommended actions.")
    print("─────────────────────────────────────────")
