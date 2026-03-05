"""Ontology-grounded RAG index with OG-RAG hyperedge retrieval and OntoRAG context enrichment.

Key capabilities:
  - Dual retrieval (key-side + value-side similarity) — OG-RAG
  - Concept-aware boost for entities mentioned in the query
  - OntoRAG-style ontological context: parents, children, definitions
  - Greedy set cover over hyperedges — OG-RAG Algorithm 2
  - Fact-level provenance for attribution
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from ontology_builder.storage.graphdb import OntologyGraph
from ontology_builder.storage.hypergraph import HyperGraph, build_hypergraph

logger = logging.getLogger(__name__)

_ENCODE_BATCH_SIZE = 64

_model: SentenceTransformer | None = None
_lock = threading.Lock()
_records: list[dict[str, Any]] = []
_key_embeddings: np.ndarray | None = None
_value_embeddings: np.ndarray | None = None
_node_names: set[str] = set()
_node_to_record_indices: dict[str, list[int]] = {}
_hyperedges: list[list[int]] = []
_graph_ref: OntologyGraph | None = None
_hypergraph_ref: HyperGraph | None = None


def _get_model() -> SentenceTransformer:
    global _model
    with _lock:
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        return _model


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------

def _graph_to_records(graph: OntologyGraph) -> list[dict[str, Any]]:
    """Convert graph to structured records for dual retrieval.

    Each record has: key, value, full (formatted fact), node, source_ref (for attribution).
    """
    g = graph.get_graph()
    records: list[dict[str, Any]] = []
    for node in g.nodes():
        data = g.nodes[node]
        node_type = data.get("type", "Entity")
        desc = data.get("description", "")
        kind = data.get("kind", "class")
        full = f"subject: {node}, attribute: type, value: {node_type}"
        if desc:
            full += f" ({desc})"
        records.append({
            "key": f"{node} type",
            "value": node_type,
            "full": full,
            "node": node,
            "kind": kind,
            "source_ref": f"node:{node}",
        })
    for u, v, data in g.edges(data=True):
        r = data.get("relation", "related_to")
        conf = data.get("confidence", 1.0)
        full = f"subject: {u}, attribute: {r}, value: {v}"
        records.append({
            "key": f"{u} {r}",
            "value": v,
            "full": full,
            "node": u,
            "kind": "edge",
            "confidence": conf,
            "source_ref": f"edge:{u}-{r}-{v}",
        })

    for dp in graph.data_properties:
        entity = dp["entity"]
        attr = dp["attribute"]
        val = dp["value"]
        full = f"subject: {entity}, attribute: {attr}, value: {val}"
        records.append({
            "key": f"{entity} {attr}",
            "value": val,
            "full": full,
            "node": entity,
            "kind": "data_property",
            "source_ref": f"dp:{entity}-{attr}",
        })
    return records


def _build_hyperedges(records: list[dict[str, Any]]) -> tuple[list[list[int]], dict[str, list[int]]]:
    """Build hyperedges: each hyperedge groups all records sharing the same node."""
    node_to_indices: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        n = rec.get("node")
        if n:
            node_to_indices.setdefault(n, []).append(i)
    hyperedges = list(node_to_indices.values())
    return hyperedges, node_to_indices


# ---------------------------------------------------------------------------
# OntoRAG ontological context enrichment
# ---------------------------------------------------------------------------

def _build_ontological_context(query: str, graph: OntologyGraph) -> str:
    """OntoRAG Eq. 2: RO(x) — retrieve ontological context for entities in the query.

    For each entity mentioned in the query, gather:
      - Parent classes (superclasses)
      - Child classes (subclasses)
      - Description/definition
    """
    if graph is None:
        return ""
    g = graph.get_graph()
    query_lower = query.lower()
    words = set(re.findall(r"\b\w+\b", query_lower))

    matched_nodes: list[str] = []
    for node in g.nodes():
        node_lower = node.lower()
        if node_lower in query_lower or any(
            w in node_lower or node_lower in w for w in words if len(w) > 2
        ):
            matched_nodes.append(node)

    if not matched_nodes:
        return ""

    lines: list[str] = []
    lines.append("=== Ontological Context ===")
    for node in matched_nodes[:5]:
        parents = graph.get_parents(node)
        children = graph.get_children(node)
        desc = graph.get_node_description(node)
        parts = [f"Entity: {node}"]
        if desc:
            parts.append(f"  Definition: {desc}")
        if parents:
            parts.append(f"  Superclasses: {', '.join(parents)}")
        if children:
            parts.append(f"  Subclasses: {', '.join(children)}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_index(graph: OntologyGraph, verbose: bool = True) -> None:
    """Build embedding index with hypergraph and ontological context support."""
    global _records, _key_embeddings, _value_embeddings, _node_names
    global _node_to_record_indices, _hyperedges, _graph_ref, _hypergraph_ref

    nodes = graph.get_graph().number_of_nodes()
    edges = graph.get_graph().number_of_edges()
    logger.info("[QAIndex] Building index | nodes=%d | edges=%d", nodes, edges)

    records = _graph_to_records(graph)
    if not records:
        with _lock:
            _records = []
            _key_embeddings = None
            _value_embeddings = None
            _node_names = set()
            _node_to_record_indices = {}
            _hyperedges = []
            _graph_ref = None
            _hypergraph_ref = None
        logger.warning("[QAIndex] Empty graph, index cleared")
        return

    hyperedges, node_to_indices = _build_hyperedges(records)

    factual_blocks = graph.to_factual_blocks()
    hg = build_hypergraph(factual_blocks)

    keys = [r["key"] for r in records]
    values = [r["value"] for r in records]
    logger.debug("[QAIndex] Encoding %d records", len(records))
    model = _get_model()
    key_chunks = []
    value_chunks = []
    for i in tqdm(
        range(0, len(records), _ENCODE_BATCH_SIZE),
        desc="Encoding records",
        disable=not verbose,
        unit="batch",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5,
    ):
        batch_keys = keys[i: i + _ENCODE_BATCH_SIZE]
        batch_values = values[i: i + _ENCODE_BATCH_SIZE]
        key_chunks.append(model.encode(batch_keys, convert_to_numpy=True))
        value_chunks.append(model.encode(batch_values, convert_to_numpy=True))
    key_emb = np.vstack(key_chunks) if key_chunks else np.array([])
    value_emb = np.vstack(value_chunks) if value_chunks else np.array([])

    with _lock:
        _records = records
        _key_embeddings = key_emb
        _value_embeddings = value_emb
        _node_names = set(graph.get_graph().nodes())
        _node_to_record_indices = node_to_indices
        _hyperedges = hyperedges
        _graph_ref = graph
        _hypergraph_ref = hg
    logger.info("[QAIndex] Index built: %d records, %d hyperedges", len(records), len(hyperedges))


def clear_index() -> None:
    global _records, _key_embeddings, _value_embeddings, _node_names
    global _node_to_record_indices, _hyperedges, _graph_ref, _hypergraph_ref
    with _lock:
        _records = []
        _key_embeddings = None
        _value_embeddings = None
        _node_names = set()
        _node_to_record_indices = {}
        _hyperedges = []
        _graph_ref = None
        _hypergraph_ref = None


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------

def _cosine_scores(query_emb: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(doc_embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-9
    return np.dot(doc_embeddings, query_emb) / norms


def _concept_matched_indices(query: str) -> set[int]:
    query_lower = query.lower()
    words = set(re.findall(r"\b\w+\b", query_lower))
    matched: set[int] = set()
    with _lock:
        node_to_indices = dict(_node_to_record_indices)
        node_names = set(_node_names)
    for node in node_names:
        node_lower = node.lower()
        if node_lower in query_lower or any(
            w in node_lower or node_lower in w for w in words if len(w) > 2
        ):
            matched.update(node_to_indices.get(node, []))
    return matched


# ---------------------------------------------------------------------------
# Public retrieval API
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """Structured retrieval result with facts and attribution."""

    facts: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    ontological_context: str = ""


def retrieve(query: str, top_k: int = 10) -> list[str]:
    """Dual retrieval with concept boost — returns fact strings."""
    with _lock:
        records = list(_records)
        key_emb = _key_embeddings
        value_emb = _value_embeddings
    if not records or key_emb is None or value_emb is None:
        return []

    model = _get_model()
    q_emb = model.encode(query, convert_to_numpy=True)
    key_scores = _cosine_scores(q_emb, key_emb)
    value_scores = _cosine_scores(q_emb, value_emb)
    top_by_key = set(np.argsort(key_scores)[::-1][:top_k])
    top_by_value = set(np.argsort(value_scores)[::-1][:top_k])
    union = top_by_key | top_by_value
    concept_matched = _concept_matched_indices(query)
    union |= concept_matched
    order = list(concept_matched) + [i for i in union if i not in concept_matched]
    seen: set[int] = set()
    result: list[str] = []
    for i in order:
        if i not in seen and i < len(records):
            seen.add(i)
            result.append(records[i]["full"])
            if len(result) >= min(2 * top_k, 20):
                break
    return result


def retrieve_with_context(query: str, top_k: int = 10) -> RetrievalResult:
    """OntoRAG + OG-RAG combined retrieval with ontological context and attribution."""
    with _lock:
        records = list(_records)
        key_emb = _key_embeddings
        value_emb = _value_embeddings
        graph = _graph_ref
    if not records or key_emb is None or value_emb is None:
        return RetrievalResult()

    model = _get_model()
    q_emb = model.encode(query, convert_to_numpy=True)
    key_scores = _cosine_scores(q_emb, key_emb)
    value_scores = _cosine_scores(q_emb, value_emb)
    top_by_key = set(np.argsort(key_scores)[::-1][:top_k])
    top_by_value = set(np.argsort(value_scores)[::-1][:top_k])
    union = top_by_key | top_by_value
    concept_matched = _concept_matched_indices(query)
    union |= concept_matched
    order = list(concept_matched) + [i for i in union if i not in concept_matched]

    facts: list[str] = []
    refs: list[str] = []
    seen: set[int] = set()
    for i in order:
        if i not in seen and i < len(records):
            seen.add(i)
            facts.append(records[i]["full"])
            refs.append(records[i].get("source_ref", ""))
            if len(facts) >= min(2 * top_k, 20):
                break

    onto_ctx = ""
    if graph is not None:
        onto_ctx = _build_ontological_context(query, graph)

    return RetrievalResult(facts=facts, source_refs=refs, ontological_context=onto_ctx)


def retrieve_hyperedges(query: str, k_nodes: int = 10, max_hyperedges: int = 5) -> list[str]:
    """OG-RAG Algorithm 2: greedy set cover over hyperedges."""
    with _lock:
        records = list(_records)
        key_emb = _key_embeddings
        value_emb = _value_embeddings
        hyperedges = list(_hyperedges)
    if not records or key_emb is None or value_emb is None or not hyperedges:
        return []

    model = _get_model()
    q_emb = model.encode(query, convert_to_numpy=True)
    key_scores = _cosine_scores(q_emb, key_emb)
    value_scores = _cosine_scores(q_emb, value_emb)
    top_by_key = set(np.argsort(key_scores)[::-1][:k_nodes])
    top_by_value = set(np.argsort(value_scores)[::-1][:k_nodes])
    relevant_indices = top_by_key | top_by_value | _concept_matched_indices(query)

    he_idx_to_indices = {i: set(he) for i, he in enumerate(hyperedges)}
    uncovered = set(relevant_indices)
    selected: list[int] = []
    remaining = set(he_idx_to_indices.keys())
    while uncovered and len(selected) < max_hyperedges:
        best_he = -1
        best_count = 0
        for he_idx in remaining:
            count = len(uncovered & he_idx_to_indices[he_idx])
            if count > best_count:
                best_count = count
                best_he = he_idx
        if best_he < 0 or best_count == 0:
            break
        selected.append(best_he)
        remaining.discard(best_he)
        uncovered -= he_idx_to_indices[best_he]

    result: list[str] = []
    seen_full: set[str] = set()
    for he_idx in selected:
        for idx in hyperedges[he_idx]:
            if idx < len(records):
                full = records[idx]["full"]
                if full not in seen_full:
                    seen_full.add(full)
                    result.append(full)
    return result
