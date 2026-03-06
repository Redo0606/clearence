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
    health_before: dict[str, Any] = field(default_factory=dict)
    health_after: dict[str, Any] = field(default_factory=dict)
    health_report_before: GraphHealthReport | None = None
    health_report_after: GraphHealthReport | None = None
    inferred_edges: list[tuple[str, str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edges_added": self.edges_added,
            "orphans_linked": self.orphans_linked,
            "components_bridged": self.components_bridged,
            "missing_relations_added": self.missing_relations_added,
            "health_before": self.health_before,
            "health_after": self.health_after,
            "inferred_edges": self.inferred_edges,
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


def _link_orphans(
    graph: OntologyGraph,
    config: RepairConfig,
    report: RepairReport,
    progress_callback: Callable[[str, str, dict], None] | None,
) -> None:
    """Link orphan nodes to similar connected nodes via embeddings."""
    g = graph.get_graph()
    orphans = [n for n in g.nodes() if g.degree(n) == 0]
    connected = [n for n in g.nodes() if g.degree(n) > 0]
    if not orphans or not connected:
        return

    if progress_callback:
        progress_callback("orphans", f"Linking {len(orphans)} orphan nodes", {"count": len(orphans)})

    orphan_texts = [_node_text(n, g.nodes[n]) for n in orphans]
    conn_texts = [_node_text(n, g.nodes[n]) for n in connected]
    orphan_embs = _get_node_embeddings(graph, orphans, orphan_texts)
    conn_embs = _get_node_embeddings(graph, connected, conn_texts)
    sim = _cosine_similarity_matrix(orphan_embs, conn_embs)

    linked = 0
    for i, orphan in enumerate(orphans):
        row = sim[i]
        top_indices = np.argsort(row)[::-1][: config.max_orphan_links]
        for j in top_indices:
            if row[j] >= config.similarity_threshold and connected[j] in g:
                target = connected[j]
                graph.add_relation(
                    orphan,
                    "related_to",
                    target,
                    confidence=DEFAULT_CONFIDENCE,
                    source_document="inferred",
                    provenance={"origin": "repair", "rule": "orphan_link"},
                )
                report.inferred_edges.append((orphan, "related_to", target))
                report.edges_added += 1
                linked += 1
    report.orphans_linked = linked


def _bridge_components(
    graph: OntologyGraph,
    config: RepairConfig,
    report: RepairReport,
    progress_callback: Callable[[str, str, dict], None] | None,
) -> None:
    """Bridge components to the largest via embedding similarity.

    By default bridges all non-largest components. Set small_component_threshold
    to only bridge components smaller than that (e.g. 10 for legacy behavior).
    """
    g = graph.get_graph()
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        return

    largest = max(components, key=len)
    # Bridge all non-largest, or only "small" ones if threshold set
    if config.small_component_threshold is not None:
        to_bridge = [c for c in components if c != largest and len(c) < config.small_component_threshold]
    else:
        to_bridge = [c for c in components if c != largest]
    if not to_bridge:
        return

    # Scale max bridges: at least cover all when many components
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

    # When many components, allow slightly lower similarity to get more bridges
    threshold = config.bridge_similarity_threshold
    if threshold is None and len(components) > 20:
        threshold = min(config.similarity_threshold, 0.70)
    elif threshold is None:
        threshold = config.similarity_threshold

    bridged = 0
    for i, rep in enumerate(reps):
        if bridged >= max_bridges:
            break
        row = sim[i]
        best_j = int(np.argmax(row))
        if row[best_j] >= threshold:
            target = largest_nodes[best_j]
            if rep in g and target in g:
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


def _add_root_concept(
    graph: OntologyGraph,
    progress_callback: Callable[[str, str, dict], None] | None,
) -> int:
    """Add Thing root and link orphan classes to it."""
    g = graph.get_graph()
    if "Thing" not in g:
        graph.add_class("Thing", description="Root concept")
    orphan_classes = [
        n for n in g.nodes()
        if g.nodes[n].get("kind") == "class" and g.degree(n) == 0 and n != "Thing"
    ]
    if not orphan_classes:
        return 0

    if progress_callback:
        progress_callback("root_concept", "Adding root concept (Thing)", {"orphan_classes": len(orphan_classes)})

    added = 0
    for node in orphan_classes:
        if not graph.has_edge(node, "Thing", "subClassOf"):
            graph.add_relation(
                node, "subClassOf", "Thing",
                confidence=DEFAULT_CONFIDENCE,
                source_document="inferred",
                provenance={"origin": "repair", "rule": "root_concept"},
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
    root_added = _add_root_concept(graph, None)
    report.edges_added += root_added
    _link_orphans(graph, cfg, report, None)
    return report


def repair_graph(
    graph: OntologyGraph,
    config: RepairConfig | None = None,
    dry_run: bool = False,
    progress_callback: Callable[[str, str, dict], None] | None = None,
    kb_id: str | None = None,
) -> RepairReport:
    """Repair graph: root concept, orphan linking, component bridging, optional reasoning.

    Computes GraphHealthReport before/after; if repair_target_met is False after first pass,
    runs a second pass (orphan linking only, cap 2 total passes). Logs health at INFO.
    """
    cfg = config or RepairConfig()
    report = RepairReport()

    if progress_callback:
        progress_callback("health_before", "Computing health before repair", {})

    report.health_before = compute_graph_health(graph, kb_id=kb_id)
    report.health_report_before = _compute_health_report(graph, cfg)

    if dry_run:
        return report

    # 1. Root concept
    root_added = _add_root_concept(graph, progress_callback)
    report.edges_added += root_added

    # 2. Orphan linking
    _link_orphans(graph, cfg, report, progress_callback)

    # 3. Component bridging
    _bridge_components(graph, cfg, report, progress_callback)

    # 4. Reasoning
    if cfg.run_reasoning_after and report.edges_added > 0:
        if progress_callback:
            progress_callback("reasoning", "Running OWL 2 RL inference", {})
        result = run_inference(graph)
        report.edges_added += result.inferred_edges

    if progress_callback:
        progress_callback("health_after", "Computing health after repair", {})

    report.health_after = compute_graph_health(graph, kb_id=kb_id)
    report.health_report_after = _compute_health_report(graph, cfg)

    # Second pass if targets not met (orphan linking only, cap 2 passes)
    if not report.health_report_after.repair_target_met and report.health_report_after.orphan_count > 0:
        if progress_callback:
            progress_callback("repair_pass2", "Second repair pass (orphans)", {})
        prev_edges = report.edges_added
        _link_orphans(graph, cfg, report, progress_callback)
        report.health_report_after = _compute_health_report(graph, cfg)
        if report.edges_added > prev_edges:
            report.health_after = compute_graph_health(graph, kb_id=kb_id)
            logger.info(
                "[Repair] Second pass added %d edges | orphan_ratio=%.2f components=%d target_met=%s",
                report.edges_added - prev_edges,
                report.health_report_after.orphan_ratio,
                report.health_report_after.component_count,
                report.health_report_after.repair_target_met,
            )

    logger.info(
        "[Repair] Health before: nodes=%d edges=%d orphans=%d components=%d target_met=%s",
        report.health_report_before.total_nodes if report.health_report_before else 0,
        report.health_report_before.total_edges if report.health_report_before else 0,
        report.health_report_before.orphan_count if report.health_report_before else 0,
        report.health_report_before.component_count if report.health_report_before else 0,
        report.health_report_before.repair_target_met if report.health_report_before else False,
    )
    logger.info(
        "[Repair] Health after: nodes=%d edges=%d orphans=%d components=%d target_met=%s",
        report.health_report_after.total_nodes if report.health_report_after else 0,
        report.health_report_after.total_edges if report.health_report_after else 0,
        report.health_report_after.orphan_count if report.health_report_after else 0,
        report.health_report_after.component_count if report.health_report_after else 0,
        report.health_report_after.repair_target_met if report.health_report_after else False,
    )
    return report
