"""Generate ontology-grounded evaluation questions from graph entities and edges."""

from __future__ import annotations

import logging
import random
from typing import Callable

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

# Target ratio: 70% single-hop, 30% multi-hop
SINGLE_HOP_RATIO = 0.7


def generate_ontology_questions(
    graph: OntologyGraph,
    num_questions: int = 5,
    retrieve_fn: Callable[[str], list[str]] | None = None,
    min_facts: int = 2,
    progress_callback: Callable[[str, int, int, str | None], None] | None = None,
) -> list[str]:
    """Generate evaluation questions from graph entities and edges.

    Args:
        graph: Ontology graph.
        num_questions: Target number of questions to return.
        retrieve_fn: Optional function to check if question retrieves enough facts.
        min_facts: Minimum facts required when retrieve_fn is used.
        progress_callback: Optional callback(phase, current, total, question).

    Returns:
        List of question strings (70% single-hop, 30% multi-hop).
    """
    num_single = max(1, int(num_questions * SINGLE_HOP_RATIO))
    num_multi = num_questions - num_single

    single_hop = _generate_single_hop_questions(
        graph, num_single, retrieve_fn, min_facts, progress_callback
    )
    multi_hop = _generate_multi_hop_questions(
        graph, num_multi, retrieve_fn, min_facts, progress_callback
    )

    questions = single_hop + multi_hop
    random.shuffle(questions)
    return questions[:num_questions]


def _generate_single_hop_questions(
    graph: OntologyGraph,
    num_questions: int,
    retrieve_fn: Callable[[str], list[str]] | None,
    min_facts: int,
    progress_callback: Callable[[str, int, int, str | None], None] | None,
) -> list[str]:
    """Generate simple single-relation questions."""
    g = graph.get_graph()
    questions: list[str] = []
    seen: set[str] = set()
    nodes = list(g.nodes())
    if progress_callback:
        progress_callback("scanning_entities", 0, len(nodes), None)
    for i, node in enumerate(nodes):
        if progress_callback and i % 10 == 0:
            progress_callback("scanning_entities", i, len(nodes), None)
        q = f"What is {node}?"
        if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
            seen.add(q)
            questions.append(q)
        if len(questions) >= num_questions:
            break

    if len(questions) < num_questions:
        edges = [(u, v, d.get("relation", "related_to")) for u, v, d in g.edges(data=True)]
        if progress_callback:
            progress_callback("scanning_edges", 0, len(edges), None)
        for i, (u, v, r) in enumerate(edges):
            if progress_callback and i % 20 == 0:
                progress_callback("scanning_edges", i, len(edges), None)
            q = f"How is {u} related to {v}?"
            if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
                seen.add(q)
                questions.append(q)
            if len(questions) >= num_questions:
                break

    if len(questions) < num_questions and len(nodes) >= 2:
        for _ in range(num_questions * 2):
            a, b = random.sample(nodes, 2)
            q = f"How are {a} and {b} related?"
            if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
                seen.add(q)
                questions.append(q)
            if len(questions) >= num_questions:
                break

    if progress_callback:
        progress_callback("done", len(questions), len(questions), None)

    return questions[:num_questions]


def _generate_multi_hop_questions(
    graph: OntologyGraph,
    num_questions: int,
    retrieve_fn: Callable[[str], list[str]] | None,
    min_facts: int,
    progress_callback: Callable[[str, int, int, str | None], None] | None,
) -> list[str]:
    """Generate multi-hop questions requiring reasoning across relations."""
    if num_questions <= 0:
        return []
    g = graph.get_graph()
    questions: list[str] = []
    seen: set[str] = set()
    nodes = list(g.nodes())

    for node in nodes:
        in_degree = g.in_degree(node)
        out_degree = g.out_degree(node)
        if in_degree + out_degree >= 3:
            q = f"What factors influence {node}?"
            if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
                seen.add(q)
                questions.append(q)
            if len(questions) >= num_questions:
                return questions[:num_questions]

    edges = list(g.edges(data=True))
    for u, v, _ in edges:
        for _, w, _ in g.out_edges(v, data=True):
            if u != w and w in nodes:
                q = f"How does {u} relate to {w}?"
                if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
                    seen.add(q)
                    questions.append(q)
                if len(questions) >= num_questions:
                    return questions[:num_questions]

    for node in nodes:
        if g.out_degree(node) >= 2:
            q = f"What does {node} affect?"
            if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
                seen.add(q)
                questions.append(q)
            if len(questions) >= num_questions:
                break

    return questions[:num_questions]


def _passes_retrieve(
    question: str,
    retrieve_fn: Callable[[str], list[str]] | None,
    min_facts: int,
) -> bool:
    """Return True if retrieve_fn is None or retrieves at least min_facts."""
    if retrieve_fn is None:
        return True
    try:
        facts = retrieve_fn(question)
        return len(facts) >= min_facts
    except Exception:
        return False
