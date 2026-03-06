"""Structured graph-grounded QA: answer natural language questions using the ontology graph.

Retrieves relevant nodes by embedding similarity, assembles 1-hop neighborhood context,
and generates an answer with the LLM. Uses graph.embedding_cache when available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from core.config import get_settings
from ontology_builder.embeddings import get_embedding_model
from ontology_builder.llm.client import complete
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

QA_GRAPH_SYSTEM = (
    "You are a knowledge graph assistant. Answer the question using only the provided graph context. "
    "If the answer is not in the context, say so."
)


@dataclass
class AnswerResult:
    """Result of graph-grounded QA."""

    answer: str
    supporting_nodes: list[str]
    confidence: float


def _get_node_embedding(graph: OntologyGraph, name: str, node_text: str):
    """Return embedding for a node (from cache or encode)."""
    cache = getattr(graph, "embedding_cache", None) or {}
    if name in cache:
        arr = cache[name]
        return np.asarray(arr, dtype=np.float32).reshape(1, -1)
    model = get_embedding_model()
    emb = model.encode(node_text, convert_to_numpy=True, show_progress_bar=False)
    cache[name] = emb
    return emb.reshape(1, -1)


def _format_node_context(graph: OntologyGraph, node: str) -> str:
    """Format one node and its 1-hop neighborhood for context."""
    g = graph.get_graph()
    if node not in g:
        return ""
    data = g.nodes[node]
    kind = data.get("kind", "class")
    desc = data.get("description", "") or ""
    lines = [f"Node: {node} (type: {kind})", f"Description: {desc}"]

    out_edges = list(g.out_edges(node, data=True))
    in_edges = list(g.in_edges(node, data=True))
    rel_parts = []
    for _, tgt, d in out_edges:
        rel = d.get("relation", "related_to")
        rel_parts.append(f"{rel} → {tgt}")
    for src, _, d in in_edges:
        rel = d.get("relation", "related_to")
        rel_parts.append(f"{rel} ← {src}")
    if rel_parts:
        lines.append("Relations: " + ", ".join(rel_parts))
    return "\n".join(lines)


def answer_question(
    question: str,
    graph: OntologyGraph,
    top_k: int = 10,
) -> AnswerResult:
    """Answer a natural language question using the ontology graph as knowledge source.

    Retrieves top_k most similar nodes by embedding, assembles their 1-hop neighborhood
    as context, truncates to qa_max_context_chars (or 6000), and calls the LLM.

    Args:
        question: User question.
        graph: Ontology graph (uses embedding_cache when available).
        top_k: Number of nodes to retrieve for context.

    Returns:
        AnswerResult with answer text, supporting node names, and confidence (0–1 heuristic).
    """
    g = graph.get_graph()
    nodes = list(g.nodes())
    if not nodes:
        return AnswerResult(answer="No graph content available.", supporting_nodes=[], confidence=0.0)

    # Embed question
    model = get_embedding_model()
    q_emb = model.encode(question, convert_to_numpy=True, show_progress_bar=False)
    q_emb = np.asarray(q_emb, dtype=np.float32).reshape(1, -1)

    # Node texts and embeddings (use cache)
    node_texts = []
    for n in nodes:
        desc = g.nodes[n].get("description", "") or ""
        node_texts.append(f"{n} {desc}".strip() or n)

    embs_list = []
    for n, txt in zip(nodes, node_texts):
        emb = _get_node_embedding(graph, n, txt)
        embs_list.append(emb)
    if not embs_list:
        return AnswerResult(answer="No graph content available.", supporting_nodes=[], confidence=0.0)
    node_embs = np.vstack(embs_list)

    # Cosine similarity
    norms = np.linalg.norm(node_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1e-9
    sims = (node_embs @ q_emb.T).ravel() / norms.ravel()
    top_indices = np.argsort(sims)[::-1][:top_k]
    supporting_nodes = [nodes[i] for i in top_indices]

    # Assemble context
    context_parts = []
    for node in supporting_nodes:
        context_parts.append(_format_node_context(graph, node))
    context = "\n\n".join(context_parts)

    max_chars = getattr(get_settings(), "qa_max_context_chars", 6000)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n[... truncated for context ...]"
        logger.debug("[AnswerGenerator] Truncated context to %d chars", max_chars)

    user_msg = f"{context}\n\nQuestion: {question}"
    try:
        response = complete(
            system=QA_GRAPH_SYSTEM,
            user=user_msg,
            temperature=0.2,
        )
        answer = (response or "").strip()
    except Exception as e:
        logger.warning("[AnswerGenerator] LLM call failed: %s", e)
        return AnswerResult(
            answer="Unable to generate an answer.",
            supporting_nodes=supporting_nodes,
            confidence=0.0,
        )

    # Confidence heuristic: fraction of retrieved nodes that contain at least one question token
    q_tokens = set(question.lower().split())
    q_tokens = {t for t in q_tokens if len(t) > 2}
    overlap_count = 0
    for node in supporting_nodes:
        node_lower = (node + " " + (g.nodes[node].get("description") or "")).lower()
        if any(t in node_lower for t in q_tokens):
            overlap_count += 1
    confidence = overlap_count / len(supporting_nodes) if supporting_nodes else 0.0

    return AnswerResult(
        answer=answer,
        supporting_nodes=supporting_nodes,
        confidence=round(confidence, 2),
    )
