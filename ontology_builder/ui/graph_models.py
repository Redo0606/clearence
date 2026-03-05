"""Data normalization layer for ontology graph visualization.

Converts OntologyGraph into a flat, validated graph model suitable for
layout engines and visualization. Handles cycles, disconnected subgraphs,
and virtual root creation.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

VIRTUAL_ROOT_ID = "__root__"


@dataclass
class GraphNode:
    """Normalized graph node for visualization."""

    id: str
    type: str  # "class" | "instance"
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Normalized graph edge for visualization."""

    id: str
    source: str
    target: str
    relation: str
    inferred: bool = False


@dataclass
class NormalizedGraph:
    """Flat graph model with validated nodes and edges."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    roots: list[str]
    has_cycles: bool
    disconnected_count: int
    clusters: list[set[str]] = field(default_factory=list)
    isolated: set[str] = field(default_factory=set)
    hierarchy_levels: dict[str, int] = field(default_factory=dict)


def _ensure_unique_ids(nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
    """Ensure all node IDs are unique; log duplicates."""
    seen: set[str] = set()
    for n in nodes:
        if n.id in seen:
            logger.warning("Duplicate node id: %s", n.id)
        seen.add(n.id)


def _ensure_no_duplicate_edges(edges: list[GraphEdge]) -> None:
    """Remove duplicate edges; keep first occurrence."""
    seen: set[tuple[str, str, str]] = set()
    to_remove = []
    for e in edges:
        key = (e.source, e.target, e.relation)
        if key in seen:
            to_remove.append(e)
        seen.add(key)
    for e in to_remove:
        edges.remove(e)
        logger.debug("Removed duplicate edge: %s -> %s (%s)", e.source, e.target, e.relation)


def _ensure_no_missing_refs(edges: list[GraphEdge], node_ids: set[str]) -> None:
    """Filter out edges referencing missing nodes."""
    valid = [e for e in edges if e.source in node_ids and e.target in node_ids]
    removed = len(edges) - len(valid)
    if removed:
        edges.clear()
        edges.extend(valid)
        logger.warning("Removed %d edges with missing node references", removed)


def _detect_cycles(edges: list[GraphEdge]) -> bool:
    """Detect cycles using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e.source, []).append(e.target)
    color: dict[str, int] = {n: WHITE for e in edges for n in (e.source, e.target)}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if color.get(neighbor) == GRAY:
                return True
            if color.get(neighbor) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in color:
        if color[node] == WHITE and dfs(node):
            return True
    return False


def _find_roots(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[str]:
    """Find root candidates: nodes with no incoming subClassOf edges."""
    has_incoming: set[str] = set()
    for e in edges:
        if e.relation == "subClassOf":
            has_incoming.add(e.target)
    node_ids = {n.id for n in nodes}
    roots = [n.id for n in nodes if n.id not in has_incoming and n.id != VIRTUAL_ROOT_ID]
    return roots if roots else list(node_ids)[:1] if node_ids else []


def _get_clusters_and_isolated(
    nodes: list[GraphNode], edges: list[GraphEdge]
) -> tuple[list[set[str]], set[str]]:
    """Return clusters (connected components) and isolated nodes (degree 0)."""
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        if e.source in adj and e.target in adj:
            adj[e.source].append(e.target)
            adj[e.target].append(e.source)
    visited: set[str] = set()
    clusters: list[set[str]] = []
    for n in nodes:
        if n.id in visited:
            continue
        cluster: set[str] = set()
        q = deque([n.id])
        while q:
            u = q.popleft()
            if u in visited:
                continue
            visited.add(u)
            cluster.add(u)
            for v in adj.get(u, []):
                if v not in visited:
                    q.append(v)
        clusters.append(cluster)
    isolated = {n.id for n in nodes if len(adj.get(n.id, [])) == 0}
    return clusters, isolated


def _compute_hierarchy_levels(
    nodes: list[GraphNode], edges: list[GraphEdge], roots: list[str]
) -> dict[str, int]:
    """BFS from roots over subClassOf edges. subClassOf A->B means A is child of B.
    Traverse from roots (parents) down to children. Level 0 = root."""
    sub_adj: dict[str, list[str]] = {}
    for e in edges:
        if e.relation == "subClassOf":
            sub_adj.setdefault(e.target, []).append(e.source)
    levels: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque((r, 0) for r in roots if r != VIRTUAL_ROOT_ID)
    for r in roots:
        if r != VIRTUAL_ROOT_ID:
            levels[r] = 0
    while q:
        u, lev = q.popleft()
        for v in sub_adj.get(u, []):
            if v not in levels:
                levels[v] = lev + 1
                q.append((v, lev + 1))
    for n in nodes:
        if n.id not in levels:
            levels[n.id] = 999
    return levels


def _count_disconnected(nodes: list[GraphNode], edges: list[GraphEdge]) -> int:
    """Count number of disconnected subgraphs using BFS."""
    clusters, _ = _get_clusters_and_isolated(nodes, edges)
    return len(clusters)


def normalize_graph(graph: "OntologyGraph") -> NormalizedGraph:
    """Convert OntologyGraph to normalized flat graph model."""
    g = graph.get_graph()

    nodes: list[GraphNode] = []
    for node_id in g.nodes():
        data = g.nodes[node_id]
        kind = data.get("kind", "class")
        node_type = "instance" if kind == "instance" else "class"
        nodes.append(
            GraphNode(
                id=node_id,
                type=node_type,
                label=node_id,
                metadata={
                    "description": data.get("description", ""),
                    "synonyms": data.get("synonyms", []),
                },
            )
        )

    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for u, v, data in g.edges(data=True):
        rel = data.get("relation", "related_to")
        key = (u, v, rel)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edge_id = f"{u}->{v}:{rel}"
        edges.append(
            GraphEdge(
                id=edge_id,
                source=u,
                target=v,
                relation=rel,
                inferred=data.get("inferred", False),
            )
        )

    node_ids = {n.id for n in nodes}
    _ensure_no_duplicate_edges(edges)
    _ensure_no_missing_refs(edges, node_ids)
    _ensure_unique_ids(nodes, edges)

    roots = _find_roots(nodes, edges)
    has_cycles = _detect_cycles(edges)
    clusters, isolated = _get_clusters_and_isolated(nodes, edges)
    disconnected_count = len(clusters)

    if not roots and nodes:
        logger.info("No root found; creating virtual root and connecting top-level classes")
        nodes.append(
            GraphNode(id=VIRTUAL_ROOT_ID, type="class", label="(root)", metadata={})
        )
        top_level = [
            n.id
            for n in nodes
            if n.id != VIRTUAL_ROOT_ID
            and not any(e.target == n.id and e.relation == "subClassOf" for e in edges)
        ]
        for nid in top_level:
            edges.append(
                GraphEdge(
                    id=f"{VIRTUAL_ROOT_ID}->{nid}:subClassOf",
                    source=VIRTUAL_ROOT_ID,
                    target=nid,
                    relation="subClassOf",
                    inferred=False,
                )
            )
        roots = [VIRTUAL_ROOT_ID]

    hierarchy_levels = _compute_hierarchy_levels(nodes, edges, roots)

    return NormalizedGraph(
        nodes=nodes,
        edges=edges,
        roots=roots,
        has_cycles=has_cycles,
        disconnected_count=disconnected_count,
        clusters=clusters,
        isolated=isolated,
        hierarchy_levels=hierarchy_levels,
    )
