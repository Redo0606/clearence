"""Graph repair: infer missing edges to reduce orphans and bridge components."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import networkx as nx
from sentence_transformers import SentenceTransformer

from ontology_builder.evaluation.graph_health import compute_graph_health
from ontology_builder.storage.graphdb import OntologyGraph
from ontology_builder.reasoning.engine import run_inference

logger = logging.getLogger(__name__)

ENCODE_BATCH_SIZE = 64
DEFAULT_CONFIDENCE = 0.85


@dataclass
class RepairConfig:
    """Configuration for graph repair."""

    similarity_threshold: float = 0.75
    max_orphan_links: int = 5
    max_component_bridges: int = 3
    add_root_concept: bool = True
    run_reasoning_after: bool = True


@dataclass
class RepairReport:
    """Result of a repair run."""

    edges_added: int = 0
    orphans_linked: int = 0
    components_bridged: int = 0
    health_before: dict[str, Any] = field(default_factory=dict)
    health_after: dict[str, Any] = field(default_factory=dict)
    inferred_edges: list[tuple[str, str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edges_added": self.edges_added,
            "orphans_linked": self.orphans_linked,
            "components_bridged": self.components_bridged,
            "health_before": self.health_before,
            "health_after": self.health_after,
            "inferred_edges": self.inferred_edges,
        }


_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _encode_batch(texts: list[str], model: SentenceTransformer) -> np.ndarray:
    """Encode texts in batches."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    embs: list[np.ndarray] = []
    for i in range(0, len(texts), ENCODE_BATCH_SIZE):
        batch = texts[i : i + ENCODE_BATCH_SIZE]
        e = model.encode(batch, normalize_embeddings=True)
        embs.append(e)
    return np.vstack(embs) if embs else np.zeros((0, 384), dtype=np.float32)


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

    model = _get_model()
    orphan_texts = [_node_text(n, g.nodes[n]) for n in orphans]
    conn_texts = [_node_text(n, g.nodes[n]) for n in connected]

    orphan_embs = _encode_batch(orphan_texts, model)
    conn_embs = _encode_batch(conn_texts, model)
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
    """Bridge small components to the largest via embedding similarity."""
    g = graph.get_graph()
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        return

    largest = max(components, key=len)
    small = [c for c in components if c != largest and len(c) < 10]
    if not small:
        return

    if progress_callback:
        progress_callback("components", f"Bridging {len(small)} components", {"count": len(small)})

    model = _get_model()
    largest_nodes = list(largest)
    reps: list[str] = []
    for c in small:
        rep = max(c, key=lambda n: g.degree(n))
        reps.append(rep)

    rep_texts = [_node_text(n, g.nodes[n]) for n in reps]
    largest_texts = [_node_text(n, g.nodes[n]) for n in largest_nodes]

    rep_embs = _encode_batch(rep_texts, model)
    largest_embs = _encode_batch(largest_texts, model)
    sim = _cosine_similarity_matrix(rep_embs, largest_embs)

    bridged = 0
    for i, rep in enumerate(reps):
        row = sim[i]
        best_j = int(np.argmax(row))
        if row[best_j] >= config.similarity_threshold:
            target = largest_nodes[best_j]
            if rep in g and target in g:
                graph.add_relation(
                    rep,
                    "related_to",
                    target,
                    confidence=DEFAULT_CONFIDENCE,
                    source_document="inferred",
                )
                report.inferred_edges.append((rep, "related_to", target))
                report.edges_added += 1
                bridged += 1
        if bridged >= config.max_component_bridges:
            break
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
            graph.add_relation(node, "subClassOf", "Thing", confidence=DEFAULT_CONFIDENCE, source_document="inferred")
            added += 1
    return added


def repair_graph(
    graph: OntologyGraph,
    config: RepairConfig | None = None,
    dry_run: bool = False,
    progress_callback: Callable[[str, str, dict], None] | None = None,
    kb_id: str | None = None,
) -> RepairReport:
    """Repair graph: root concept, orphan linking, component bridging, optional reasoning."""
    cfg = config or RepairConfig()
    report = RepairReport()

    if progress_callback:
        progress_callback("health_before", "Computing health before repair", {})

    report.health_before = compute_graph_health(graph, kb_id=kb_id)

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
    return report
