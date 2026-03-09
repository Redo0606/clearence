"""Generate exploration questions from the reasoning graph for multi-step KB querying."""

from __future__ import annotations

import json
import logging
from typing import Any

from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.llm.client import complete
from ontology_builder.llm.json_repair import repair_json

logger = logging.getLogger(__name__)

# Language names for exploration-question instruction
_LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
}


def _question_language_instruction(ontology_language: str | None) -> str:
    """Return instruction so exploration questions match the ontology and user query language."""
    if not ontology_language or ontology_language.lower() == "en":
        return (
            "\n\nLANGUAGE: Generate questions in the SAME language as the user's original question. "
            "If the user asked in French, all questions must be in French. If in English, use English."
        )
    name = _LANGUAGE_NAMES.get(ontology_language.lower(), ontology_language)
    return (
        f"\n\nLANGUAGE (critical): The ontology and user query are in {name}. "
        f"Generate ALL exploration questions strictly in {name}. "
        "Do not switch to English. Use exact concept names from the graph in that language."
    )


QUESTION_GEN_SYSTEM = """\
You generate ontology exploration questions to gather knowledge from a knowledge base.

Given:
1. The user's original question
2. The current reasoning graph (concepts and relations discovered so far)
3. Conversation context: what questions were already asked and what facts were retrieved
4. Detected gaps: concepts without definitions, missing relations

Your task: Generate 1–4 exploration questions that would retrieve useful facts to answer the user's question.

GRAPH LANGUAGE RULES (critical for retrieval quality):
- The KB stores facts as "subject: X, attribute: R, value: Y". Retrieval uses semantic search.
- Use EXACT concept names from the graph in your questions (e.g. if the graph has "midlaner", use "midlaner" not "mid laner").
- Phrase questions to match ontology structure: "What is [concept]?", "What is the [relation] between [concept] and [concept]?", "What [attribute] does [concept] have?"
- Prefer questions that reference specific concepts from the graph (nodes, relation types) for better retrieval.
- Avoid vague or generic questions; be specific to the domain and concepts already discovered.

CONTEXT AWARENESS:
- Do NOT repeat questions already asked. Do NOT ask about concepts that already have definitions.
- Prioritize questions that address detected gaps (missing definitions, missing relations).
- Build on what was found: if step X found "A relates to B", ask about related concepts (e.g. "What affects B?").
- Each question should be self-contained and answerable by a KB retrieval.

Output: Return ONLY valid JSON with a "questions" key containing a list of strings.
"""


def generate_exploration_questions(
    original_query: str,
    graph: ReasoningGraph,
    previous_questions: list[str] | None = None,
    steps: list[dict[str, Any]] | None = None,
    gaps: list[dict[str, Any]] | None = None,
    ontology_language: str | None = None,
) -> list[str]:
    """Generate exploration questions based on the current reasoning graph state.

    Args:
        original_query: User's original question.
        graph: Current reasoning graph with concepts and edges.
        previous_questions: Questions already asked (to avoid duplicates).
        steps: Conversation context: list of {question, answer, concepts, relations} from prior steps.
        gaps: Detected ontology gaps (missing_concept, missing_relation) to address.
        ontology_language: ISO 639-1 language of the KB. Questions are generated in this language.

    Returns:
        List of 1–4 exploration questions.
    """
    previous_questions = previous_questions or []
    steps = steps or []
    gaps = gaps or []
    graph_dict = graph.to_dict()

    steps_summary = []
    for i, s in enumerate(steps, 1):
        q = s.get("question", "")
        facts_preview = (s.get("answer") or "")[:200]
        if facts_preview and facts_preview != "(no facts)":
            steps_summary.append(f"  Step {i}: Q: {q} → Found: {facts_preview}...")
        else:
            steps_summary.append(f"  Step {i}: Q: {q} → (no facts)")

    gaps_summary = []
    for g in gaps:
        gt = g.get("gap_type", "")
        if gt == "missing_concept":
            gaps_summary.append(f"  - Missing definition for: {g.get('subject', '')}")
        elif gt == "missing_relation":
            gaps_summary.append(f"  - Missing relation: {g.get('subject', '')} → {g.get('relation', '')} → {g.get('target', '')}")

    lang_instruction = _question_language_instruction(ontology_language)
    system_prompt = QUESTION_GEN_SYSTEM + lang_instruction

    user_prompt = f"""Original question: {original_query}

Current reasoning graph:
{json.dumps(graph_dict, indent=2)}

Conversation so far (questions asked and facts retrieved):
{chr(10).join(steps_summary) if steps_summary else "  (none yet)"}

Previous questions already asked: {json.dumps(previous_questions)}

Detected gaps to address:
{chr(10).join(gaps_summary) if gaps_summary else "  (none)"}

Generate 1–4 new exploration questions. Use exact concept names from the graph. Reply with JSON only: {{"questions": [...]}}"""

    try:
        response = complete(
            system=system_prompt,
            user=user_prompt,
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning("[OntologyQuestioner] LLM failed: %s", e)
        return _fallback_questions(graph, previous_questions, ontology_language)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(repair_json(response))
        except (json.JSONDecodeError, TypeError):
            return _fallback_questions(graph, previous_questions, ontology_language)

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


# Fallback question templates by language (used when LLM fails)
_FALLBACK_TEMPLATES = {
    "en": "What is {concept}?",
    "fr": "Qu'est-ce que {concept} ?",
    "de": "Was ist {concept}?",
    "es": "¿Qué es {concept}?",
    "it": "Cos'è {concept}?",
    "pt": "O que é {concept}?",
    "nl": "Wat is {concept}?",
    "ar": "ما هو {concept}؟",
    "zh": "{concept}是什么？",
    "ja": "{concept}とは何ですか？",
    "ko": "{concept}란 무엇인가요?",
    "ru": "Что такое {concept}?",
}


def _fallback_questions(
    graph: ReasoningGraph,
    previous: list[str],
    ontology_language: str | None = None,
) -> list[str]:
    """Rule-based fallback when LLM fails."""
    template = _FALLBACK_TEMPLATES.get(
        (ontology_language or "en").lower()[:2],
        _FALLBACK_TEMPLATES["en"],
    )
    prev_set = {p.strip().lower() for p in previous}
    result = []
    for node in graph.nodes.values():
        if not node.definition:
            q = template.format(concept=node.concept)
            if q.lower() not in prev_set:
                result.append(q)
                prev_set.add(q.lower())
        if len(result) >= 3:
            break
    return result
