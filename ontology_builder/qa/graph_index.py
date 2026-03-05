"""
Build and query an embedding index over the ontology graph for RAG retrieval.
OG-RAG-style: dual retrieval (key + value similarity), structured facts, concept-aware boost,
optional hyperedge-based greedy set cover.
Reuses SentenceTransformer (all-MiniLM-L6-v2).
"""
import logging
import re
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from ontology_builder.storage.graphdb import OntologyGraph

_ENCODE_BATCH_SIZE = 64

_model: SentenceTransformer | None = None
_lock = threading.Lock()
_records: list[dict[str, Any]] = []
_key_embeddings: np.ndarray | None = None
_value_embeddings: np.ndarray | None = None
_node_names: set[str] = set()
_node_to_record_indices: dict[str, list[int]] = {}
_hyperedges: list[list[int]] = []  # each hyperedge = list of record indices


def _get_model() -> SentenceTransformer:
    global _model
    with _lock:
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        return _model


def _graph_to_records(graph: OntologyGraph) -> list[dict[str, Any]]:
    """Convert graph to structured records for dual retrieval.

    Each record has: key (subject+attribute for key-side similarity), value (for value-side
    similarity), full (formatted fact string), node (for concept-aware boost when query
    mentions the node name).
    """
    g = graph.get_graph()
    records: list[dict[str, Any]] = []
    for node in g.nodes():
        data = g.nodes[node]
        node_type = data.get("type", "Entity")
        key = f"{node} type"
        value = node_type
        full = f"subject: {node}, attribute: type, value: {node_type}"
        records.append({"key": key, "value": value, "full": full, "node": node})
    for u, v, data in g.edges(data=True):
        r = data.get("relation", "related_to")
        key = f"{u} {r}"
        value = v
        full = f"subject: {u}, attribute: {r}, value: {v}"
        records.append({"key": key, "value": value, "full": full, "node": u})
    return records


def _build_hyperedges(records: list[dict[str, Any]], g: Any) -> tuple[list[list[int]], dict[str, list[int]]]:
    """Build hyperedges for greedy set cover: each hyperedge = one node + all its records.

    Greedy selection picks hyperedges that cover the most uncovered relevant nodes.
    """
    node_to_indices: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        n = rec.get("node")
        if n:
            node_to_indices.setdefault(n, []).append(i)
    hyperedges = list(node_to_indices.values())
    return hyperedges, node_to_indices


def build_index(graph: OntologyGraph, verbose: bool = True) -> None:
    """Build embedding index from graph; store structured records and embeddings."""
    global _records, _key_embeddings, _value_embeddings, _node_names, _node_to_record_indices, _hyperedges
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
        logger.warning("[QAIndex] Empty graph, index cleared")
        return
    g = graph.get_graph()
    hyperedges, node_to_indices = _build_hyperedges(records, g)
    keys = [r["key"] for r in records]
    values = [r["value"] for r in records]
    logger.debug("[QAIndex] Encoding %d records with SentenceTransformer", len(records))
    model = _get_model()
    key_chunks = []
    value_chunks = []
    batch_ranges = range(0, len(records), _ENCODE_BATCH_SIZE)
    for i in tqdm(batch_ranges, desc="Encoding records", disable=not verbose, unit="batch", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        batch_keys = keys[i : i + _ENCODE_BATCH_SIZE]
        batch_values = values[i : i + _ENCODE_BATCH_SIZE]
        key_chunks.append(model.encode(batch_keys, convert_to_numpy=True))
        value_chunks.append(model.encode(batch_values, convert_to_numpy=True))
    key_emb = np.vstack(key_chunks) if key_chunks else np.array([])
    value_emb = np.vstack(value_chunks) if value_chunks else np.array([])
    with _lock:
        _records = records
        _key_embeddings = key_emb
        _value_embeddings = value_emb
        _node_names = set(g.nodes())
        _node_to_record_indices = node_to_indices
        _hyperedges = hyperedges
    logger.info("QA index built: %d records", len(records))


def clear_index() -> None:
    """Clear the cached index."""
    global _records, _key_embeddings, _value_embeddings, _node_names, _node_to_record_indices, _hyperedges
    with _lock:
        _records = []
        _key_embeddings = None
        _value_embeddings = None
        _node_names = set()
        _node_to_record_indices = {}
        _hyperedges = []


def _cosine_scores(query_emb: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and each document embedding."""
    norms = np.linalg.norm(doc_embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-9
    return np.dot(doc_embeddings, query_emb) / norms


def _concept_matched_indices(query: str) -> set[int]:
    """Return record indices whose node name appears in the query (concept-aware boost)."""
    query_lower = query.lower()
    words = set(re.findall(r"\b\w+\b", query_lower))
    matched: set[int] = set()
    with _lock:
        node_to_indices = dict(_node_to_record_indices)
        node_names = set(_node_names)
    for node in node_names:
        node_lower = node.lower()
        if node_lower in query_lower or any(w in node_lower or node_lower in w for w in words if len(w) > 2):
            matched.update(node_to_indices.get(node, []))
    return matched


def retrieve(query: str, top_k: int = 10) -> list[str]:
    """
    OG-RAG-style dual retrieval: top_k by key similarity + top_k by value similarity.
    Concept-aware boost: prepend snippets for nodes that appear in the query.
    Returns union of results, deduplicated, capped at 2*top_k.
    """
    with _lock:
        records = list(_records)
        key_emb = _key_embeddings
        value_emb = _value_embeddings
    if not records or key_emb is None or value_emb is None:
        logger.debug("[QAIndex] Retrieve: empty index")
        return []
    logger.debug("[QAIndex] Retrieving | query_len=%d | top_k=%d | records=%d", len(query), top_k, len(records))
    model = _get_model()
    q_emb = model.encode(query, convert_to_numpy=True)
    key_scores = _cosine_scores(q_emb, key_emb)
    value_scores = _cosine_scores(q_emb, value_emb)
    # Dual retrieval: union of top-k by key similarity and top-k by value similarity
    top_by_key = set(np.argsort(key_scores)[::-1][:top_k])
    top_by_value = set(np.argsort(value_scores)[::-1][:top_k])
    union = top_by_key | top_by_value
    # Concept boost: prepend facts for nodes mentioned in the query
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
    logger.debug("[QAIndex] Retrieve complete | snippets=%d", len(result))
    return result


def retrieve_hyperedges(query: str, k_nodes: int = 10, max_hyperedges: int = 5) -> list[str]:
    """
    OG-RAG-style greedy hyperedge selection: get relevant nodes via dual retrieval,
    then greedily select hyperedges that cover the most uncovered nodes.
    """
    with _lock:
        records = list(_records)
        key_emb = _key_embeddings
        value_emb = _value_embeddings
        hyperedges = list(_hyperedges)
    if not records or key_emb is None or value_emb is None or not hyperedges:
        logger.debug("[QAIndex] Retrieve hyperedges: empty index")
        return []
    logger.debug("[QAIndex] Retrieving hyperedges | query_len=%d | k_nodes=%d | max_hyperedges=%d",
                 len(query), k_nodes, max_hyperedges)
    model = _get_model()
    q_emb = model.encode(query, convert_to_numpy=True)
    key_scores = _cosine_scores(q_emb, key_emb)
    value_scores = _cosine_scores(q_emb, value_emb)
    top_by_key = set(np.argsort(key_scores)[::-1][:k_nodes])
    top_by_value = set(np.argsort(value_scores)[::-1][:k_nodes])
    relevant_indices = top_by_key | top_by_value | _concept_matched_indices(query)
    # Greedy set cover: repeatedly pick hyperedge covering most uncovered relevant indices
    he_idx_to_indices = {i: set(he) for i, he in enumerate(hyperedges)}
    uncovered = set(relevant_indices)
    result_he_indices: list[int] = []
    remaining = set(he_idx_to_indices.keys())
    while uncovered and len(result_he_indices) < max_hyperedges:
        best_he = -1
        best_count = -1
        for he_idx in remaining:
            indices = he_idx_to_indices[he_idx]
            count = len(uncovered & indices)
            if count > best_count:
                best_count = count
                best_he = he_idx
        if best_he < 0 or best_count == 0:
            break
        result_he_indices.append(best_he)
        remaining.discard(best_he)
        uncovered -= he_idx_to_indices[best_he]
    result: list[str] = []
    seen_full: set[str] = set()
    for he_idx in result_he_indices:
        for idx in hyperedges[he_idx]:
            full = records[idx]["full"]
            if full not in seen_full:
                seen_full.add(full)
                result.append(full)
    return result
