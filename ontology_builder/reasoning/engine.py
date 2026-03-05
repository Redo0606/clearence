"""
Apply axiom-style rules (transitive and symmetric closure) to the ontology graph.
Deterministic, no LLM in the hot path.
"""
import logging

import networkx as nx

from ontology_builder.reasoning.rules import (
    DOMAIN_RULES,
    SYMMETRIC_RELATIONS,
    TRANSITIVE_RELATIONS,
)
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def apply_transitive_closure(graph: OntologyGraph, relation_names: set[str]) -> int:
    """Compute transitive closure for given relations and add new edges.

    For each relation r: if A r B and B r C, add A r C.

    Args:
        graph: OntologyGraph to update.
        relation_names: Set of relation names to apply closure to.

    Returns:
        Number of edges added.
    """
    g = graph.get_graph()
    added = 0
    logger.debug("[Reasoning] Transitive closure | relations=%s", relation_names)
    for r in relation_names:
        edges_r = [(u, v) for u, v, data in g.edges(data=True) if data.get("relation") == r]
        if not edges_r:
            logger.debug("[Reasoning] No edges for relation %r, skipping", r)
            continue
        temp = nx.DiGraph(edges_r)
        try:
            H = nx.transitive_closure(temp)
        except Exception as e:
            logger.debug("[Reasoning] Transitive closure failed for %r | error=%s", r, e)
            continue
        new_edges = set(H.edges()) - set(temp.edges())
        if new_edges:
            logger.debug("[Reasoning] Relation %r: adding %d transitive edges", r, len(new_edges))
        for u, v in new_edges:
            if not g.has_edge(u, v):
                graph.add_relation(u, r, v)
                added += 1
    return added


def apply_symmetric_closure(graph: OntologyGraph, relation_names: set[str]) -> int:
    """Add reverse edges for symmetric relations.

    For each (u, v) with relation in relation_names, add (v, u) if missing.

    Args:
        graph: OntologyGraph to update.
        relation_names: Set of symmetric relation names.

    Returns:
        Number of edges added.
    """
    g = graph.get_graph()
    to_add: list[tuple[str, str, str]] = []
    logger.debug("[Reasoning] Symmetric closure | relations=%s", relation_names)
    for u, v, data in g.edges(data=True):
        r = data.get("relation")
        if r in relation_names and not g.has_edge(v, u):
            to_add.append((v, u, r))
    if to_add:
        logger.debug("[Reasoning] Adding %d symmetric reverse edges", len(to_add))
    for a, b, r in to_add:
        graph.add_relation(a, r, b)
    return len(to_add)


def run_inference(graph: OntologyGraph, subject: str | None = None) -> int:
    """Apply transitive and symmetric closure based on rules.

    Uses TRANSITIVE_RELATIONS, SYMMETRIC_RELATIONS, and optionally DOMAIN_RULES
    when subject matches a domain keyword.

    Args:
        graph: OntologyGraph to update.
        subject: Optional document subject for domain-specific rules.

    Returns:
        Total number of edges added.
    """
    nodes_before = graph.get_graph().number_of_nodes()
    edges_before = graph.get_graph().number_of_edges()
    logger.info("[Reasoning] Starting axiom-based inference | nodes=%d | edges=%d | subject=%s",
                nodes_before, edges_before, subject)

    transitive = set(TRANSITIVE_RELATIONS)
    symmetric = set(SYMMETRIC_RELATIONS)
    if subject:
        subject_lower = subject.lower().strip()
        for key, rules in DOMAIN_RULES.items():
            if key in subject_lower or subject_lower in key:
                transitive.update(rules.get("transitive", []))
                symmetric.update(rules.get("symmetric", []))
                break
    # Normalize relation names in graph: we compare with data.get("relation") which may be str
    trans_added = apply_transitive_closure(graph, transitive)
    sym_added = apply_symmetric_closure(graph, symmetric)
    added = trans_added + sym_added
    logger.info("[Reasoning] Complete | transitive_added=%d | symmetric_added=%d | total_added=%d",
                trans_added, sym_added, added)
    return added
