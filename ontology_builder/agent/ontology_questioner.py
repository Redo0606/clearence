"""Generate exploration questions from the reasoning graph for multi-step KB querying."""

from __future__ import annotations

import json
import logging

from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.llm.client import complete
from ontology_builder.llm.json_repair import repair_json

logger = logging.getLogger(__name__)

QUESTION_GEN_SYSTEM = """\
You generate ontology exploration questions to gather knowledge from a knowledge base.

Given:
1. The user's original question
2. The current reasoning graph (concepts and relations discovered so far)

Your task: Generate 1–4 natural language questions that would retrieve useful facts to answer the user's question.

Rules:
- Define unknown concepts: "What is X?" for concepts without definitions
- Discover relationships: "What relates X to Y?", "What stats affect X?"
- Identify optimization targets: "What items increase X?", "What combinations optimize Y?"
- Each question should be self-contained and answerable by a KB retrieval
- Return ONLY valid JSON with a "questions" key containing a list of strings
- Do NOT repeat questions already answered in previous steps
"""


def generate_exploration_questions(
    original_query: str,
    graph: ReasoningGraph,
    previous_questions: list[str] | None = None,
) -> list[str]:
    """Generate exploration questions based on the current reasoning graph state.

    Args:
        original_query: User's original question.
        graph: Current reasoning graph with concepts and edges.
        previous_questions: Questions already asked (to avoid duplicates).

    Returns:
        List of 1–4 exploration questions.
    """
    previous_questions = previous_questions or []
    graph_dict = graph.to_dict()

    user_prompt = f"""Original question: {original_query}

Current reasoning graph:
{json.dumps(graph_dict, indent=2)}

Previous questions already asked: {json.dumps(previous_questions)}

Generate 1–4 new exploration questions. Reply with JSON only: {{"questions": [...]}}"""

    try:
        response = complete(
            system=QUESTION_GEN_SYSTEM,
            user=user_prompt,
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning("[OntologyQuestioner] LLM failed: %s", e)
        return _fallback_questions(graph, previous_questions)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(repair_json(response))
        except (json.JSONDecodeError, TypeError):
            return _fallback_questions(graph, previous_questions)

    questions = parsed.get("questions", [])
    if not isinstance(questions, list):
        questions = [q for q in (questions,) if isinstance(q, str)]

    result = []
    seen = set(q.strip().lower() for q in previous_questions)
    for q in questions:
        if isinstance(q, str) and q.strip():
            norm = q.strip()
            if norm.lower() not in seen:
                seen.add(norm.lower())
                result.append(norm)

    return result[:4]


def _fallback_questions(graph: ReasoningGraph, previous: list[str]) -> list[str]:
    """Rule-based fallback when LLM fails."""
    prev_set = {p.strip().lower() for p in previous}
    result = []
    for node in graph.nodes.values():
        if not node.definition:
            q = f"What is {node.concept}?"
            if q.lower() not in prev_set:
                result.append(q)
                prev_set.add(q.lower())
        if len(result) >= 3:
            break
    return result
