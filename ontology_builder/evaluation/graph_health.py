"""Graph health metrics for ontology quality assessment.

Computes structural (connectivity, density, orphans), semantic (relation types,
unlabeled nodes), and retrieval (index coverage) metrics. Used by the Evaluate
tab and repair module.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def compute_graph_health(
    graph: "OntologyGraph",
    kb_id: str | None = None,
) -> dict[str, Any]:
    """Compute structural, semantic, and retrieval health metrics.

    Returns a dict with:
      - structural: node_count, edge_count, density, connected_components,
        orphan_nodes, edge_to_node_ratio, avg_degree, max_degree, degree_std,
        largest_component_coverage
      - semantic: unlabeled_nodes_pct, unique_relation_types, relation_type_entropy,
        avg_property_count, class_instance_ratio
      - retrieval: index_record_count (placeholder), hyperedge_count, facts_per_node,
        hyperedge_coverage
      - overall_score: 0-100
      - badge: "Healthy" | "Needs Attention" | "Critical"
      - kb_id: when provided
    """
    g = graph.get_graph()
    n = g.number_of_nodes()
    m = g.number_of_edges()

    if n == 0:
        return {
            "structural": {
                "node_count": 0,
                "edge_count": 0,
                "edge_to_node_ratio": 0.0,
                "density": 0.0,
                "connected_components": 0,
                "largest_component_coverage": 0.0,
                "avg_degree": 0.0,
                "max_degree": 0,
                "degree_std": 0.0,
                "orphan_nodes": 0,
            },
            "semantic": {
                "unlabeled_nodes_pct": 0.0,
                "unique_relation_types": 0,
                "relation_type_entropy": 0.0,
                "avg_property_count": 0.0,
                "class_instance_ratio": 0.0,
            },
            "retrieval": {
                "index_record_count": 0,
                "hyperedge_count": 0,
                "facts_per_node": 0.0,
                "hyperedge_coverage": 0.0,
            },
            "overall_score": 0.0,
            "badge": "Empty",
            **({"kb_id": kb_id} if kb_id else {}),
        }

    # Structural
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    largest_size = max(len(c) for c in components) if components else 0
    largest_coverage = largest_size / n if n > 0 else 0.0

    degrees = [d for _, d in g.degree()]
    avg_deg = sum(degrees) / n if n > 0 else 0.0
    max_deg = max(degrees) if degrees else 0
    var_deg = sum((d - avg_deg) ** 2 for d in degrees) / n if n > 0 else 0.0
    std_deg = math.sqrt(var_deg) if var_deg >= 0 else 0.0

    orphans = sum(1 for _, d in g.degree() if d == 0)
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0.0
    edge_to_node = m / n if n > 0 else 0.0

    # Semantic
    unlabeled = sum(1 for node in g.nodes() if not g.nodes[node].get("type"))
    unlabeled_pct = 100.0 * unlabeled / n if n > 0 else 0.0

    rel_types: set[str] = set()
    for _, _, d in g.edges(data=True):
        r = d.get("relation", "related_to")
        rel_types.add(r)
    rel_count = len(rel_types)

    rel_counts: dict[str, int] = {}
    for _, _, d in g.edges(data=True):
        r = d.get("relation", "related_to")
        rel_counts[r] = rel_counts.get(r, 0) + 1
    total_edges = sum(rel_counts.values()) or 1
    entropy = -sum((c / total_edges) * math.log2(c / total_edges) for c in rel_counts.values())

    prop_counts = [len([k for k in g.nodes[n].keys() if k not in ("type", "kind")]) for n in g.nodes()]
    avg_props = sum(prop_counts) / n if n > 0 else 0.0

    classes = sum(1 for n in g.nodes() if g.nodes[n].get("kind") == "class")
    instances = sum(1 for n in g.nodes() if g.nodes[n].get("kind") == "instance")
    class_instance_ratio = classes / instances if instances > 0 else float(classes)

    # Retrieval (facts = edges + node type facts)
    facts = m + n  # approximate
    facts_per_node = facts / n if n > 0 else 0.0
    hyperedge_count = n  # nodes as hyperedge anchors
    hyperedge_coverage = 1.0 if n > 0 else 0.0

    structural = {
        "node_count": n,
        "edge_count": m,
        "edge_to_node_ratio": round(edge_to_node, 3),
        "density": round(density, 4),
        "connected_components": len(components),
        "largest_component_coverage": round(largest_coverage, 3),
        "avg_degree": round(avg_deg, 2),
        "max_degree": max_deg,
        "degree_std": round(std_deg, 2),
        "orphan_nodes": orphans,
    }
    semantic = {
        "unlabeled_nodes_pct": round(unlabeled_pct, 1),
        "unique_relation_types": rel_count,
        "relation_type_entropy": round(entropy, 3),
        "avg_property_count": round(avg_props, 2),
        "class_instance_ratio": round(class_instance_ratio, 2),
    }
    retrieval = {
        "index_record_count": facts,
        "hyperedge_count": hyperedge_count,
        "facts_per_node": round(facts_per_node, 2),
        "hyperedge_coverage": hyperedge_coverage,
    }

    score, badge = _health_score(structural, semantic, retrieval)
    result: dict[str, Any] = {
        "structural": structural,
        "semantic": semantic,
        "retrieval": retrieval,
        "overall_score": score,
        "badge": badge,
    }
    if kb_id:
        result["kb_id"] = kb_id
    return result


def _health_score(
    structural: dict[str, Any],
    semantic: dict[str, Any],
    retrieval: dict[str, Any],
) -> tuple[float, str]:
    """Compute overall score 0-100 and badge."""
    orphans = structural.get("orphan_nodes", 0)
    components = structural.get("connected_components", 1)
    edge_to_node = structural.get("edge_to_node_ratio", 0.0)
    n = structural.get("node_count", 1)
    orphan_pct = 100.0 * orphans / n if n > 0 else 0.0

    score = 100.0
    if orphan_pct > 5:
        score -= min(30, orphan_pct * 2)
    if components > 10:
        score -= min(25, (components - 10) * 2)
    if edge_to_node < 2.0:
        score -= min(20, (2.0 - edge_to_node) * 10)
    score = max(0.0, min(100.0, score))

    if score >= 80:
        badge = "Healthy"
    elif score >= 50:
        badge = "Needs Attention"
    else:
        badge = "Critical"
    return round(score, 1), badge


def health_with_score(health: dict[str, Any]) -> dict[str, Any]:
    """Ensure health dict has overall_score and badge. Idempotent."""
    if "overall_score" in health and "badge" in health:
        return health
    structural = health.get("structural", {})
    semantic = health.get("semantic", {})
    retrieval = health.get("retrieval", {})
    score, badge = _health_score(structural, semantic, retrieval)
    return {**health, "overall_score": score, "badge": badge}


def load_graph_health(kb_id: str, reports_dir: str | Path) -> dict[str, Any] | None:
    """Load cached health from reports dir. Returns None if missing or kb_id mismatch."""
    path = Path(reports_dir) / f"health-{kb_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("kb_id") != kb_id:
            logger.warning("Health cache kb_id mismatch: expected %s, got %s", kb_id, data.get("kb_id"))
            return None
        return data
    except Exception as e:
        logger.warning("Failed to load health cache %s: %s", path, e)
        return None


def save_graph_health(kb_id: str, health: dict[str, Any], reports_dir: str | Path) -> None:
    """Save health to reports dir."""
    path = Path(reports_dir)
    path.mkdir(parents=True, exist_ok=True)
    out = path / f"health-{kb_id}.json"
    data = {**health, "kb_id": kb_id}
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
