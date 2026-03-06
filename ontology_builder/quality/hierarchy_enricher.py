"""Hierarchy enrichment: deepen flat hierarchies (low depth variance) via LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np

from ontology_builder.embeddings import get_embedding_model
from ontology_builder.llm.client import complete
from ontology_builder.llm.json_repair import repair_json
from ontology_builder.quality.structural_scorer import StructuralMetrics
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

HIERARCHY_CLUSTER_PROMPT = """\
These ontology classes are currently all at the same level with no hierarchy between them: {classes}.

Should any of them be a subclass of another? If yes, suggest a parent-child pair (one pair only).
If no hierarchy is appropriate, reply with exactly: NONE.

Reply as JSON: {{ "parent": "<ClassName>", "child": "<ClassName>" }} or {{ "parent": null, "child": null }}.
"""

CROWDED_LEVEL_PROMPT = """\
These classes are all siblings at the same hierarchy level: {classes}.

Suggest 2–4 intermediate parent classes that would group them more meaningfully.
Only suggest groupings that are semantically justified.
Reply as JSON: {{ "intermediate_parents": [ {{ "name": "<NewParent>", "children": ["<Child1>", "<Child2>"] }} ] }}
If no grouping is appropriate, reply: {{ "intermediate_parents": [] }}
"""


def enrich_hierarchy(
    graph: OntologyGraph,
    metrics: StructuralMetrics,
    config: Any,
) -> int:
    """Add subClassOf edges to improve depth/breadth variance. Returns number of new edges."""
    if not getattr(config, "enrich_hierarchy_if_low_quality", True):
        return 0
    g = graph.get_graph()
    added = 0

    # Low depth variance: cluster depth-1 leaves (direct children of Thing with no children) by embedding
    if metrics.depth_variance < 0.5:
        depth_one_children = []
        for n, data in g.nodes(data=True):
            if data.get("kind") != "class" or n == "Thing":
                continue
            if not graph.has_edge(n, "Thing", "subClassOf"):
                continue
            has_children = any(g.has_edge(v, n) and g[v][n].get("relation") == "subClassOf" for v in g if v != n)
            if not has_children:
                depth_one_children.append(n)
        if depth_one_children:
            cache = getattr(graph, "embedding_cache", None) or {}
            model = get_embedding_model()
            texts = [f"{n} {g.nodes[n].get('description','')}" for n in depth_one_children]
            embs = []
            for i, n in enumerate(depth_one_children):
                if n in cache:
                    embs.append(np.asarray(cache[n], dtype=np.float32))
                else:
                    e = model.encode(texts[i], convert_to_numpy=True, show_progress_bar=False)
                    cache[n] = e
                    embs.append(e)
            if embs:
                embs = np.vstack(embs)
                n = len(depth_one_children)
                sim = np.dot(embs, embs.T)
                norms = np.linalg.norm(embs, axis=1, keepdims=True)
                norms[norms == 0] = 1e-9
                sim = sim / (norms * norms.T)
                np.fill_diagonal(sim, 0)
                clustered: set[int] = set()
                for i in range(n):
                    if i in clustered:
                        continue
                    cluster = [i]
                    for j in range(n):
                        if j != i and sim[i, j] >= 0.75:
                            cluster.append(j)
                            clustered.add(j)
                    clustered.add(i)
                    if len(cluster) < 2 or len(cluster) > 5:
                        continue
                    names = [depth_one_children[k] for k in cluster]
                    try:
                        raw = complete(
                            system="You are an ontology engineer. Reply only with valid JSON.",
                            user=HIERARCHY_CLUSTER_PROMPT.format(classes=json.dumps(names)),
                        )
                        data = repair_json(raw or "{}")
                        if isinstance(data, dict) and data.get("parent") and data.get("child"):
                            parent, child = data["parent"], data["child"]
                            if parent in names and child in names and parent != child and not graph.has_edge(child, parent, "subClassOf"):
                                graph.add_relation(
                                    child, "subClassOf", parent,
                                    confidence=0.75,
                                    source_document="inferred",
                                    provenance={"origin": "enrichment", "rule": "cluster_parent_child"},
                                )
                                added += 1
                    except Exception as e:
                        logger.debug("[Enricher] Cluster LLM failed: %s", e)

    # Low breadth variance: crowded level -> intermediate parents
    if metrics.breadth_variance < 5 and metrics.max_breadth > 0:
        level_counts: dict[int, list[str]] = {}
        hierarchy = _level_map(graph)
        for level, nodes in hierarchy.items():
            level_counts.setdefault(level, []).extend(nodes)
        avg_b = metrics.avg_breadth
        for level, nodes in level_counts.items():
            if len(nodes) <= 3 * avg_b:
                continue
            try:
                raw = complete(
                    system="You are an ontology engineer. Reply only with valid JSON.",
                    user=CROWDED_LEVEL_PROMPT.format(classes=json.dumps(nodes[:30])),
                )
                data = repair_json(raw or "{}")
                inters = data.get("intermediate_parents", [])
                if not isinstance(inters, list):
                    continue
                for item in inters:
                    if not isinstance(item, dict):
                        continue
                    new_parent = item.get("name", "").strip()
                    children = item.get("children", [])
                    if not new_parent or not children:
                        continue
                    if new_parent not in g:
                        graph.add_class(new_parent, description="Intermediate (enrichment)")
                    for c in children:
                        if c in g and not graph.has_edge(c, new_parent, "subClassOf"):
                            graph.add_relation(
                                c, "subClassOf", new_parent,
                                confidence=0.75,
                                source_document="inferred",
                                provenance={"origin": "enrichment", "rule": "intermediate_parent"},
                            )
                            added += 1
            except Exception as e:
                logger.debug("[Enricher] Crowded level LLM failed: %s", e)

    if added:
        logger.info("[Enricher] Added %d hierarchy edges", added)
    return added


def _level_map(graph: OntologyGraph) -> dict[int, list[str]]:
    """Map depth level -> list of class names (BFS from Thing)."""
    g = graph.get_graph()
    level_to_nodes: dict[int, list[str]] = {}
    if "Thing" not in g:
        return level_to_nodes
    level_to_nodes[0] = ["Thing"]
    visited = {"Thing"}
    frontier = ["Thing"]
    depth = 0
    while frontier:
        next_frontier = []
        for u in frontier:
            for _, v, data in g.out_edges(u, data=True):
                if data.get("relation") == "subClassOf" and v not in visited:
                    visited.add(v)
                    next_frontier.append(v)
                    level_to_nodes.setdefault(depth + 1, []).append(v)
        depth += 1
        frontier = next_frontier
    return level_to_nodes
