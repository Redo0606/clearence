"""Graph repair: infer missing edges to reduce orphans and bridge components."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import networkx as nx

from ontology_builder.embeddings import get_embedding_dimension, get_embedding_model
from ontology_builder.evaluation.graph_health import compute_graph_health
from ontology_builder.storage.graphdb import OntologyGraph
from ontology_builder.reasoning.engine import run_inference

logger = logging.getLogger(__name__)

ENCODE_BATCH_SIZE = 64
DEFAULT_CONFIDENCE = 0.85


@dataclass
class GraphHealthReport:
    """Structural health metrics for repair targeting."""

    total_nodes: int = 0
    total_edges: int = 0
    orphan_count: int = 0
    component_count: int = 0
    largest_component_size: int = 0
    orphan_ratio: float = 0.0
    fragmentation_ratio: float = 0.0
    avg_degree: float = 0.0
    repair_target_met: bool = False


@dataclass
class RepairConfig:
    """Configuration for graph repair."""

    similarity_threshold: float = 0.75
    max_orphan_links: int = 5
    max_component_bridges: int = 50
    small_component_threshold: int | None = None
    bridge_similarity_threshold: float | None = None
    add_root_concept: bool = True
    root_concept_name: str | None = None  # If set, use this; else infer domain-aware root
    run_reasoning_after: bool = True
    repair_incremental: bool = True
    repair_llm_batch_size: int = 20
    repair_use_llm_relations: bool = True
    max_missing_relation_pairs: int = 200
    orphan_ratio_target: float = 0.05
    component_count_target: int = 3
    enrich_hierarchy_if_low_quality: bool = True
    boost_population_if_sparse: bool = True
    auto_resolve_critical: bool = False
    repair_internet_definitions: bool = False
    repair_iterations: int = 1
    min_fidelity: float = 0.3  # Confidence threshold for web definitions (0–1); filters low-quality sources


def _compute_health_report(graph: OntologyGraph, config: RepairConfig) -> GraphHealthReport:
    """Compute GraphHealthReport for repair targeting."""
    g = graph.get_graph()
    n = g.number_of_nodes()
    m = g.number_of_edges()
    if n == 0:
        return GraphHealthReport(repair_target_met=True)
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    orphan_count = sum(1 for _, d in g.degree() if d == 0)
    largest = max(len(c) for c in components) if components else 0
    avg_degree = (2 * m) / n if n > 0 else 0.0
    orphan_ratio = orphan_count / n if n > 0 else 0.0
    fragmentation_ratio = len(components) / n if n > 0 else 0.0
    repair_target_met = (
        orphan_ratio < config.orphan_ratio_target
        and len(components) <= config.component_count_target
    )
    return GraphHealthReport(
        total_nodes=n,
        total_edges=m,
        orphan_count=orphan_count,
        component_count=len(components),
        largest_component_size=largest,
        orphan_ratio=orphan_ratio,
        fragmentation_ratio=fragmentation_ratio,
        avg_degree=avg_degree,
        repair_target_met=repair_target_met,
    )


@dataclass
class RepairReport:
    """Result of a repair run."""

    edges_added: int = 0
    orphans_linked: int = 0
    components_bridged: int = 0
    missing_relations_added: int = 0
    gaps_repaired: int = 0
    iterations_completed: int = 0
    health_before: dict[str, Any] = field(default_factory=dict)
    health_after: dict[str, Any] = field(default_factory=dict)
    health_report_before: GraphHealthReport | None = None
    health_report_after: GraphHealthReport | None = None
    inferred_edges: list[tuple[str, str, str]] = field(default_factory=list)
    definitions_added: dict[str, str] = field(default_factory=dict)
    iteration_summaries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edges_added": self.edges_added,
            "orphans_linked": self.orphans_linked,
            "components_bridged": self.components_bridged,
            "missing_relations_added": self.missing_relations_added,
            "gaps_repaired": self.gaps_repaired,
            "iterations_completed": self.iterations_completed,
            "health_before": self.health_before,
            "health_after": self.health_after,
            "inferred_edges": [list(e) for e in self.inferred_edges],
            "definitions_added": self.definitions_added,
            "iteration_summaries": self.iteration_summaries,
        }


def _encode_batch(texts: list[str], model) -> np.ndarray:
    """Encode texts in batches."""
    dim = get_embedding_dimension()
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)
    embs: list[np.ndarray] = []
    for i in range(0, len(texts), ENCODE_BATCH_SIZE):
        batch = texts[i : i + ENCODE_BATCH_SIZE]
        e = model.encode(batch, normalize_embeddings=True)
        embs.append(e)
    return np.vstack(embs) if embs else np.zeros((0, dim), dtype=np.float32)


def _get_node_embeddings(
    graph: OntologyGraph,
    node_list: list[str],
    node_texts: list[str],
) -> np.ndarray:
    """Return embeddings for nodes, using graph.embedding_cache when available."""
    cache = getattr(graph, "embedding_cache", None) or {}
    model = get_embedding_model()
    to_encode: list[int] = []
    dim = get_embedding_dimension()
    result = np.zeros((len(node_list), dim), dtype=np.float32)
    for i, (node, text) in enumerate(zip(node_list, node_texts)):
        if node in cache:
            arr = cache[node]
            result[i] = arr if hasattr(arr, "shape") else np.array(arr, dtype=np.float32)
        else:
            to_encode.append(i)
    if to_encode:
        batch_texts = [node_texts[j] for j in to_encode]
        batch_embs = _encode_batch(batch_texts, model)
        for k, j in enumerate(to_encode):
            result[j] = batch_embs[k]
            cache[node_list[j]] = batch_embs[k]
    return result


def _cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity: (n_a, dim) @ (dim, n_b) -> (n_a, n_b)."""
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    return np.dot(a, b.T)


def _node_text(node: str, data: dict[str, Any]) -> str:
    """Text representation for embedding: name + description."""
    desc = data.get("description", "")
    return f"{node} {desc}".strip() or node


def _node_combined_text(
    graph: OntologyGraph,
    node: str,
    data: dict[str, Any],
) -> str:
    """Combined text for semantic orphan matching: description + data props + relation targets."""
    parts = [data.get("description", "")]
    for dp in getattr(graph, "data_properties", []) or []:
        if dp.get("entity") == node:
            parts.append(str(dp.get("value", "")))
    g = graph.get_graph()
    for _, target, d in g.out_edges(node, data=True):
        if d.get("relation") not in ("subClassOf", "type"):
            parts.append(target)
    combined = " ".join(filter(None, parts))
    return combined.strip() or node


def _link_orphans(
    graph: OntologyGraph,
    config: RepairConfig,
    report: RepairReport,
    progress_callback: Callable[[str, str, dict], None] | None,
) -> None:
    """Link orphan nodes to similar connected nodes via embeddings.

    Enhanced: tries combined text (description + data props + relation targets) first;
    falls back to name-only when combined is empty. Links orphan to target's parent when
    match has cosine >= 0.75 to preserve hierarchy.
    """
    g = graph.get_graph()
    orphans = [n for n in g.nodes() if g.degree(n) == 0]
    connected = [n for n in g.nodes() if g.degree(n) > 0]
    if not orphans or not connected:
        return

    if progress_callback:
        progress_callback("orphans", f"Linking {len(orphans)} orphan nodes", {"count": len(orphans)})

    # Build combined texts for semantic matching
    orphan_combined = [_node_combined_text(graph, n, g.nodes[n]) for n in orphans]
    conn_combined = [_node_combined_text(graph, n, g.nodes[n]) for n in connected]
    use_combined = any(t != n for t, n in zip(orphan_combined, orphans)) or any(
        t != c for t, c in zip(conn_combined, connected)
    )

    if use_combined:
        orphan_texts = orphan_combined
        conn_texts = conn_combined
    else:
        orphan_texts = [_node_text(n, g.nodes[n]) for n in orphans]
        conn_texts = [_node_text(n, g.nodes[n]) for n in connected]

    orphan_embs = _get_node_embeddings(graph, orphans, orphan_texts)
    conn_embs = _get_node_embeddings(graph, connected, conn_texts)
    sim = _cosine_similarity_matrix(orphan_embs, conn_embs)

    semantic_threshold = 0.75
    name_threshold = config.similarity_threshold

    linked = 0
    for i, orphan in enumerate(orphans):
        row = sim[i]
        top_indices = np.argsort(row)[::-1][: config.max_orphan_links]
        thresh = semantic_threshold if use_combined else name_threshold
        for j in top_indices:
            if row[j] >= thresh and connected[j] in g:
                target = connected[j]
                # Link to target's parent when possible to preserve hierarchy
                parent = None
                for _, p, d in g.out_edges(target, data=True):
                    if d.get("relation") == "subClassOf":
                        parent = p
                        break
                link_to = parent if parent and parent in g else target
                if link_to == target or not graph.has_edge(orphan, link_to, "related_to"):
                    graph.add_relation(
                        orphan,
                        "related_to",
                        link_to,
                        confidence=DEFAULT_CONFIDENCE,
                        source_document="inferred",
                        provenance={"origin": "repair", "rule": "orphan_link"},
                    )
                    report.inferred_edges.append((orphan, "related_to", link_to))
                    report.edges_added += 1
                    linked += 1
                    if parent and link_to == parent:
                        logger.info("[Repair] Orphan linked via semantic match: %s -> %s (parent of %s)", orphan, parent, target)
                    break
    report.orphans_linked = linked


def _bridge_components(
    graph: OntologyGraph,
    config: RepairConfig,
    report: RepairReport,
    progress_callback: Callable[[str, str, dict], None] | None,
) -> None:
    """Bridge components to the largest via embedding similarity.

    Multi-hop: looks for intermediate node semantically between the two bridge nodes.
    If intermediate_score >= 0.6, adds A -> intermediate -> B. Else direct bridge.
    """
    g = graph.get_graph()
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        return

    largest = max(components, key=len)
    if config.small_component_threshold is not None:
        to_bridge = [c for c in components if c != largest and len(c) < config.small_component_threshold]
    else:
        to_bridge = [c for c in components if c != largest]
    if not to_bridge:
        return

    max_bridges = min(len(components) - 1, config.max_component_bridges)

    if progress_callback:
        progress_callback("components", f"Bridging {len(to_bridge)} components", {"count": len(to_bridge)})

    largest_nodes = list(largest)
    reps: list[str] = []
    for c in to_bridge:
        rep = max(c, key=lambda n: g.degree(n))
        reps.append(rep)

    rep_texts = [_node_text(n, g.nodes[n]) for n in reps]
    largest_texts = [_node_text(n, g.nodes[n]) for n in largest_nodes]
    rep_embs = _get_node_embeddings(graph, reps, rep_texts)
    largest_embs = _get_node_embeddings(graph, largest_nodes, largest_texts)
    sim = _cosine_similarity_matrix(rep_embs, largest_embs)

    threshold = config.bridge_similarity_threshold
    if threshold is None and len(components) > 20:
        threshold = min(config.similarity_threshold, 0.70)
    elif threshold is None:
        threshold = config.similarity_threshold

    # Non-component nodes (in largest) for intermediate search
    comp_sets = set(frozenset(c) for c in to_bridge)
    all_nodes = list(g.nodes())
    all_texts = [_node_text(n, g.nodes[n]) for n in all_nodes]
    all_embs = _get_node_embeddings(graph, all_nodes, all_texts)

    bridged = 0
    for i, rep in enumerate(reps):
        if bridged >= max_bridges:
            break
        row = sim[i]
        best_j = int(np.argmax(row))
        if row[best_j] >= threshold:
            target = largest_nodes[best_j]
            if rep not in g or target not in g:
                continue

            # Find intermediate node: max (sim(node, A) + sim(node, B)) / 2 over non-component nodes
            rep_emb = rep_embs[i : i + 1]
            tgt_emb = largest_embs[best_j : best_j + 1]
            sim_to_rep = _cosine_similarity_matrix(all_embs, rep_emb).flatten()
            sim_to_tgt = _cosine_similarity_matrix(all_embs, tgt_emb).flatten()
            intermediate_scores = (sim_to_rep + sim_to_tgt) / 2.0

            best_intermediate_idx = -1
            best_score = 0.0
            rep_comp = next((c for c in to_bridge if rep in c), set())
            for j in range(len(all_nodes)):
                node = all_nodes[j]
                if node == rep or node == target:
                    continue
                if node in rep_comp or any(node in c for c in to_bridge):
                    continue
                if intermediate_scores[j] > best_score:
                    best_score = intermediate_scores[j]
                    best_intermediate_idx = j

            if best_intermediate_idx >= 0 and best_score >= 0.6:
                intermediate = all_nodes[best_intermediate_idx]
                graph.add_relation(
                    rep,
                    "related_to",
                    intermediate,
                    confidence=DEFAULT_CONFIDENCE,
                    source_document="inferred",
                    provenance={"origin": "repair", "rule": "component_bridge"},
                )
                graph.add_relation(
                    intermediate,
                    "related_to",
                    target,
                    confidence=DEFAULT_CONFIDENCE,
                    source_document="inferred",
                    provenance={"origin": "repair", "rule": "component_bridge"},
                )
                report.inferred_edges.append((rep, "related_to", intermediate))
                report.inferred_edges.append((intermediate, "related_to", target))
                report.edges_added += 2
                bridged += 1
                logger.info("[Repair] Multi-hop bridge: %s -> %s -> %s", rep, intermediate, target)
            else:
                graph.add_relation(
                    rep,
                    "related_to",
                    target,
                    confidence=DEFAULT_CONFIDENCE,
                    source_document="inferred",
                    provenance={"origin": "repair", "rule": "component_bridge"},
                )
                report.inferred_edges.append((rep, "related_to", target))
                report.edges_added += 1
                bridged += 1
    report.components_bridged = bridged


def _infer_root_concept_name(graph: OntologyGraph, kb_path: str | None = None) -> str:
    """Infer a domain-aware root concept name from the graph and KB metadata."""
    try:
        from ontology_builder.enrichment.query_planner import _infer_domain_hint
        domain = _infer_domain_hint(graph, kb_path)
        if domain:
            safe = domain.replace(" ", "").replace("'", "")[:30]
            return f"{safe}Root" if safe else "DomainRoot"
    except Exception:
        pass
    return "DomainRoot"


def _add_root_concept(
    graph: OntologyGraph,
    progress_callback: Callable[[str, str, dict], None] | None,
    root_name: str | None = None,
    kb_path: str | None = None,
) -> int:
    """Add domain-aware root concept and link orphan classes to it.
    Uses root_name if provided, else infers from graph (e.g. PokemonRoot for Pokémon ontology)."""
    g = graph.get_graph()
    root = root_name or _infer_root_concept_name(graph, kb_path)
    desc = f"Root concept for this ontology" if root == "DomainRoot" else f"Root concept for {root.replace('Root','')} domain"
    if root not in g:
        graph.add_class(root, description=desc)
    orphan_classes = [
        n for n in g.nodes()
        if g.nodes[n].get("kind") == "class" and g.degree(n) == 0 and n != root
    ]
    if not orphan_classes:
        return 0

    if progress_callback:
        progress_callback("root_concept", f"Linking orphan classes to {root}", {"orphan_classes": len(orphan_classes), "root": root})

    added = 0
    for node in orphan_classes:
        if not graph.has_edge(node, root, "subClassOf"):
            graph.add_relation(
                node, "subClassOf", root,
                confidence=DEFAULT_CONFIDENCE,
                source_document="inferred",
                provenance={"origin": "repair", "rule": "root_concept", "root": root},
            )
            added += 1
    return added


def repair_graph_incremental(
    graph: OntologyGraph,
    config: RepairConfig | None = None,
) -> RepairReport:
    """Lightweight repair after each chunk merge: root concept + immediate orphan linking only.

    No component bridging or LLM calls. Used during pipeline merge loop.
    """
    cfg = config or RepairConfig()
    report = RepairReport()
    root_added = _add_root_concept(graph, None, root_name=cfg.root_concept_name)
    report.edges_added += root_added
    _link_orphans(graph, cfg, report, None)
    return report


def _run_one_repair_iteration(
    graph: OntologyGraph,
    cfg: RepairConfig,
    report: RepairReport,
    iteration: int,
    total_iterations: int,
    progress_callback: Callable[[str, str, dict], None] | None,
    kb_id: str | None,
    kb_path: str | None,
) -> None:
    """Run one repair iteration: gap repair, root, orphans, bridges, reasoning, optional pass2."""
    from pathlib import Path

    def _prog(step: str, msg: str, data: dict | None = None):
        d = dict(data or {})
        d["iteration"] = iteration
        d["iteration_total"] = total_iterations
        if progress_callback:
            progress_callback(step, msg, d)

    def _wrapped_progress(step: str, msg: str, details: dict) -> None:
        _prog(step, msg, details)

    # 0. Internet definition repair
    if cfg.repair_internet_definitions:
        from ontology_builder.repair.gap_repair import detect_gaps_in_graph, reify_definitions_from_web
        gaps = detect_gaps_in_graph(graph, kb_path=Path(kb_path) if kb_path else None)
        if gaps:
            _prog("gap_repair", f"Searching web for {len(gaps)} missing definitions", {"count": len(gaps)})
            gap_report = reify_definitions_from_web(
                graph,
                gaps,
                kb_path=Path(kb_path) if kb_path else None,
                min_fidelity=cfg.min_fidelity,
                progress_callback=lambda s, m, d: _prog("gap_repair", m, d),
                cancel_check=None,
            )
            report.gaps_repaired += gap_report.gaps_repaired
            report.definitions_added.update(gap_report.definitions_added)
            logger.info("[Repair] Iter %d: %d definitions added", iteration, gap_report.gaps_repaired)
        else:
            _prog("gap_repair", "No gaps (all concepts have descriptions)", {})

    # 1. Root concept (domain-aware)
    root_name = cfg.root_concept_name or _infer_root_concept_name(graph, kb_path)
    _prog("root_concept", f"Linking orphans to {root_name}", {})
    root_added = _add_root_concept(graph, _wrapped_progress, root_name=root_name, kb_path=kb_path)
    report.edges_added += root_added

    # 2. Orphan linking
    _link_orphans(graph, cfg, report, _wrapped_progress)

    # 3. Component bridging
    _bridge_components(graph, cfg, report, _wrapped_progress)

    # 4. Reasoning
    if cfg.run_reasoning_after and report.edges_added > 0:
        _prog("reasoning", "Running OWL 2 RL inference", {})
        result = run_inference(graph)
        report.edges_added += result.inferred_edges

    # 5. Second pass if targets not met
    health_after = _compute_health_report(graph, cfg)
    if not health_after.repair_target_met and health_after.orphan_count > 0:
        _prog("repair_pass2", "Second pass (orphans)", {})
        _link_orphans(graph, cfg, report, _wrapped_progress)


def repair_graph(
    graph: OntologyGraph,
    config: RepairConfig | None = None,
    dry_run: bool = False,
    progress_callback: Callable[[str, str, dict], None] | None = None,
    kb_id: str | None = None,
    kb_path: str | None = None,
) -> RepairReport:
    """Repair graph iteratively: optional internet definition fill, root, orphans, bridges, reasoning.

    When repair_iterations > 1, runs multiple passes. After each iteration rescans the graph
    (health + gaps) to assess the new state. Logs health at INFO.
    """
    cfg = config or RepairConfig()
    report = RepairReport()
    iterations = max(1, min(cfg.repair_iterations, 5))

    def _prog(step: str, msg: str, data: dict | None = None):
        if progress_callback:
            progress_callback(step, msg, data or {})

    _prog("health_before", "Computing health before repair", {})
    report.health_before = compute_graph_health(graph, kb_id=kb_id)
    report.health_report_before = _compute_health_report(graph, cfg)

    if dry_run:
        return report

    for it in range(1, iterations + 1):
        _prog("iteration_start", f"Iteration {it}/{iterations}", {"iteration": it, "iteration_total": iterations})
        logger.info("[Repair] Starting iteration %d/%d", it, iterations)

        _run_one_repair_iteration(
            graph, cfg, report, it, iterations,
            progress_callback, kb_id, kb_path,
        )

        report.health_after = compute_graph_health(graph, kb_id=kb_id)
        report.health_report_after = _compute_health_report(graph, cfg)

        # Rescan: gaps after this iteration
        from ontology_builder.repair.gap_repair import detect_gaps_in_graph
        from pathlib import Path
        gaps_after = detect_gaps_in_graph(graph, kb_path=Path(kb_path) if kb_path else None, max_gaps=20)
        summary = {
            "iteration": it,
            "health": report.health_after,
            "gaps_remaining": len(gaps_after),
            "gaps_sample": gaps_after[:5],
            "edges_added_so_far": report.edges_added,
            "gaps_repaired_so_far": report.gaps_repaired,
        }
        report.iteration_summaries.append(summary)
        report.iterations_completed = it

        _prog("rescan", f"Rescan: {report.health_report_after.total_nodes} nodes, {len(gaps_after)} gaps remaining", {
            "iteration": it,
            "iteration_total": iterations,
            "rescan": summary,
        })
        logger.info(
            "[Repair] Iter %d done: nodes=%d edges=%d orphans=%d gaps_remaining=%d",
            it,
            report.health_report_after.total_nodes,
            report.health_report_after.total_edges,
            report.health_report_after.orphan_count,
            len(gaps_after),
        )

    logger.info(
        "[Repair] Health before: nodes=%d edges=%d orphans=%d components=%d",
        report.health_report_before.total_nodes if report.health_report_before else 0,
        report.health_report_before.total_edges if report.health_report_before else 0,
        report.health_report_before.orphan_count if report.health_report_before else 0,
        report.health_report_before.component_count if report.health_report_before else 0,
    )
    logger.info(
        "[Repair] Health after: nodes=%d edges=%d orphans=%d components=%d iterations=%d",
        report.health_report_after.total_nodes if report.health_report_after else 0,
        report.health_report_after.total_edges if report.health_report_after else 0,
        report.health_report_after.orphan_count if report.health_report_after else 0,
        report.health_report_after.component_count if report.health_report_after else 0,
        report.iterations_completed,
    )
    return report
