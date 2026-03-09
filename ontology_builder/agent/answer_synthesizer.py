"""Synthesize final answer from the reasoning graph using the QA answer module."""

from __future__ import annotations

import logging

from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.qa.answer import QAResult, answer_question

logger = logging.getLogger(__name__)


def synthesize_answer(
    original_query: str,
    graph: ReasoningGraph,
    answer_language: str | None = None,
) -> QAResult:
    """Build context from the reasoning graph and generate final answer.

    Args:
        original_query: User's original question.
        graph: Reasoning graph with concepts and relations.
        answer_language: Optional ISO 639-1 code for answer language.

    Returns:
        QAResult with answer, reasoning, sources.
    """
    context = graph.to_context_string()
    if not context.strip():
        return QAResult(
            answer="I could not find enough information in the knowledge base to answer your question.",
            reasoning="No relevant concepts or relations were discovered during exploration.",
            sources=[],
            num_facts_used=0,
        )

    # Use graph facts as context; source_refs from graph edges
    context_lines = context.strip().split("\n")
    source_refs = [f"graph:{i}" for i in range(len(context_lines))]

    return answer_question(
        question=original_query,
        context_snippets=context_lines,
        source_refs=source_refs,
        ontological_context="",
        answer_language=answer_language,
        agent_mode=True,
    )
