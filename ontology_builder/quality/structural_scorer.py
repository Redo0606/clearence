"""Structural quality metrics from class hierarchy (Fernández et al.).

Depth/breadth variance and population metrics predict ontology reliability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

ROOT_NAME = "Thing"


@dataclass
class StructuralMetrics:
    """Structural metrics from the class hierarchy and graph."""

    # Depth profile (from BFS from root)
    max_depth: int = 0
    min_depth: int = 0
    avg_depth: float = 0.0
    depth_variance: float = 0.0

    # Breadth profile (nodes per level)
    max_breadth: int = 0
    min_breadth: int = 0
    avg_breadth: float = 0.0
    breadth_variance: float = 0.0

    # Population
    num_classes: int = 0
    num_instances: int = 0
    num_properties: int = 0
    instance_to_class_ratio: float = 0.0

    # Relation diversity (P2-6)
    subclass_ratio: float = 0.0
    generic_relation_ratio: float = 0.0
    named_relation_ratio: float = 0.0
    unique_relation_types: int = 0


@dataclass
class ReliabilityScore:
    """Single quality signal from structural metrics (paper thresholds)."""

    score: float = 0.0
    grade: str = "F"
    reasons: list[str] = field(default_factory=list)
    metrics: StructuralMetrics | None = None


def _extract_class_hierarchy(graph: OntologyGraph) -> nx.DiGraph:
    """Extract subgraph: only class nodes and subClassOf edges."""
    g = graph.get_graph()
    out = nx.DiGraph()
    for n, data in g.nodes(data=True):
        if data.get("kind") != "class":
            continue
        out.add_node(n, **data)
    for u, v, data in g.edges(data=True):
        if data.get("relation") != "subClassOf":
            continue
        if u in out and v in out:
            out.add_edge(u, v, **data)
    return out


def _depth_profile(hierarchy: nx.DiGraph) -> list[int]:
    """BFS from root; return list of depth per class (root = 0).

    Edges are stored child -> parent (subClassOf(child, parent)), so the root
    has out_degree 0 and we traverse to children via predecessors (in_edges).
    """
    if ROOT_NAME not in hierarchy:
        # Root = node that does not point to any parent (out_degree 0)
        roots = [n for n in hierarchy if hierarchy.out_degree(n) == 0]
        if not roots:
            return []
        start = roots[0]
    else:
        start = ROOT_NAME
        if start not in hierarchy:
            return []

    depths: dict[str, int] = {start: 0}
    queue = [start]
    while queue:
        u = queue.pop(0)
        d = depths[u]
        # Children are nodes that have an edge TO u (child -> parent)
        for v in hierarchy.predecessors(u):
            if v not in depths:
                depths[v] = d + 1
                queue.append(v)
    # Include any class not reached (disconnected) as depth 0 for variance
    for n in hierarchy:
        if n not in depths:
            depths[n] = 0
    return list(depths.values())


def _breadth_profile(hierarchy: nx.DiGraph, depths: list[int]) -> list[int]:
    """Count nodes per depth level."""
    if not depths:
        return []
    level_counts: dict[int, int] = {}
    for d in depths:
        level_counts[d] = level_counts.get(d, 0) + 1
    max_d = max(level_counts.keys()) if level_counts else 0
    return [level_counts.get(i, 0) for i in range(max_d + 1)]


def compute_structural_metrics(graph: OntologyGraph) -> StructuralMetrics:
    """Compute depth, breadth, population, and relation diversity metrics."""
    g = graph.get_graph()
    hierarchy = _extract_class_hierarchy(graph)

    m = StructuralMetrics()
    m.num_classes = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "class")
    m.num_instances = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "instance")
    rel_types = set()
    subclass_edges = 0
    generic_edges = 0
    total_edges = g.number_of_edges()
    for _, _, data in g.edges(data=True):
        r = data.get("relation", "related_to")
        rel_types.add(r)
        if r == "subClassOf":
            subclass_edges += 1
        if r in ("related_to", "type"):
            generic_edges += 1
    m.num_properties = len(rel_types)
    m.unique_relation_types = len(rel_types)
    m.instance_to_class_ratio = (m.num_instances / m.num_classes) if m.num_classes > 0 else 0.0
    m.subclass_ratio = (subclass_edges / total_edges) if total_edges > 0 else 0.0
    m.generic_relation_ratio = (generic_edges / total_edges) if total_edges > 0 else 0.0
    named_count = total_edges - subclass_edges - generic_edges
    m.named_relation_ratio = (named_count / total_edges) if total_edges > 0 else 0.0

    if hierarchy.number_of_nodes() == 0:
        return m

    depths = _depth_profile(hierarchy)
    if not depths:
        return m
    depths_arr = np.array(depths, dtype=float)
    m.max_depth = int(np.max(depths_arr))
    m.min_depth = int(np.min(depths_arr))
    m.avg_depth = float(np.mean(depths_arr))
    m.depth_variance = float(np.var(depths_arr))

    level_sizes = _breadth_profile(hierarchy, depths)
    if not level_sizes:
        return m
    sizes_arr = np.array(level_sizes, dtype=float)
    m.max_breadth = int(np.max(sizes_arr))
    m.min_breadth = int(np.min(sizes_arr))
    m.avg_breadth = float(np.mean(sizes_arr))
    m.breadth_variance = float(np.var(sizes_arr))

    return m


def _grade(score: float) -> str:
    if score >= 0.8:
        return "A"
    if score >= 0.6:
        return "B"
    if score >= 0.4:
        return "C"
    if score >= 0.2:
        return "D"
    return "F"


def compute_reliability_score(metrics: StructuralMetrics) -> ReliabilityScore:
    """Translate metrics into a single quality signal (paper thresholds)."""
    score = 0.0
    reasons: list[str] = []

    if metrics.depth_variance >= 0.9:
        score += 0.30
        reasons.append("HIGH depth_variance (≥0.9): strong reliability signal")
    elif metrics.depth_variance >= 0.5:
        score += 0.15
        reasons.append("MODERATE depth_variance")

    if metrics.breadth_variance >= 20:
        score += 0.25
        reasons.append("HIGH breadth_variance (≥20): strong reliability signal")
    elif metrics.breadth_variance >= 5:
        score += 0.12
        reasons.append("MODERATE breadth_variance")

    if metrics.max_breadth >= 100:
        score += 0.20
        reasons.append("HIGH max_breadth (≥100)")
    elif metrics.max_breadth >= 30:
        score += 0.08
        reasons.append("MODERATE max_breadth")

    if metrics.instance_to_class_ratio >= 1.0:
        score += 0.15
        reasons.append("RICH population (instances ≥ classes)")
    elif metrics.instance_to_class_ratio >= 0.3:
        score += 0.07
        reasons.append("MODERATE population")

    if metrics.max_depth >= 5:
        score += 0.10
        reasons.append("GOOD max_depth (≥5 levels)")
    elif metrics.max_depth >= 3:
        score += 0.05
        reasons.append("MODERATE max_depth")

    if metrics.named_relation_ratio >= 0.3:
        score += 0.10
        reasons.append("GOOD named relation diversity")
    elif metrics.named_relation_ratio >= 0.15:
        score += 0.05
        reasons.append("MODERATE named relation diversity")

    if metrics.generic_relation_ratio >= 0.6:
        score -= 0.15
        reasons.append("WARNING: high generic_relation_ratio — consider re-running repair with LLM relation inference enabled")

    score = min(score, 1.0)
    grade = _grade(score)
    if score < 0.4:
        reasons.append("Low overall structural quality — consider hierarchy enrichment and population booster")
    return ReliabilityScore(score=score, grade=grade, reasons=reasons, metrics=metrics)
