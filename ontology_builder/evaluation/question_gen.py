"""Generate ontology-grounded evaluation questions from graph entities and edges."""

from __future__ import annotations

import logging
import random
from typing import Callable

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


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
        List of question strings.
    """
    g = graph.get_graph()
    questions: list[str] = []
    seen: set[str] = set()

    # Entity-based questions
    nodes = list(g.nodes())
    if progress_callback:
        progress_callback("scanning_entities", 0, len(nodes), None)
    for i, node in enumerate(nodes):
        if progress_callback and i % 10 == 0:
            progress_callback("scanning_entities", i, len(nodes), None)
        data = g.nodes[node]
        kind = data.get("kind", "class")
        q = f"What is {node}?"
        if q not in seen and _passes_retrieve(q, retrieve_fn, min_facts):
            seen.add(q)
            questions.append(q)
        if len(questions) >= num_questions:
            break

    # Edge-based questions (How is X related to Y?)
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

    # Multi-entity questions (How are X and Y related?)
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
