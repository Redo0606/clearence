"""Generate answers from retrieved ontology facts with fact-level attribution.

Supports both simple (list[str]) and structured (RetrievalResult) context.
"""

from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field

from core.config import get_settings
from ontology_builder.llm.client import complete, complete_batch
from ontology_builder.qa.prompts import (
    AGENT_QA_SYSTEM,
    QA_SYSTEM,
    build_agent_qa_user_prompt,
    build_qa_user_prompt,
)

logger = logging.getLogger(__name__)


def _parse_answer_from_response(response_text: str) -> str:
    """Extract answer from JSON response; fallback to raw text."""
    try:
        parsed = json.loads(response_text)
        return (parsed.get("answer") or response_text).strip()
    except (json.JSONDecodeError, TypeError):
        return response_text.strip()

# Regex to strip raw source IDs ([node:X], [edge:A-R-B], [dp:E-A]) if LLM echoes them
_RAW_ID_PATTERN = re.compile(r"\s*\[(?:node|edge|dp):[^\]]+\]\s*", re.IGNORECASE)


@dataclass
class QAResult:
    """Structured QA answer with source attribution and reasoning."""

    answer: str = ""
    reasoning: str = ""
    sources: list[str] = field(default_factory=list)
    ontological_context: str = ""
    num_facts_used: int = 0


def source_ref_to_label(ref: str) -> str:
    """Convert node:X, edge:A-R-B, dp:E-A to human-readable labels for UI display."""
    if not ref:
        return ref
    if ref.startswith("node:"):
        return ref[5:].strip()
    if ref.startswith("edge:"):
        rest = ref[5:].strip()
        parts = rest.split("-", 2)
        if len(parts) == 3:
            return f"{parts[0]} → {parts[2]}"
        return rest.replace("-", " → ")
    if ref.startswith("dp:"):
        return ref[3:].strip().replace("-", " = ")
    return ref


def answer_question(
    question: str,
    context_snippets: list[str],
    source_refs: list[str] | None = None,
    ontological_context: str = "",
    answer_language: str | None = None,
    agent_mode: bool = False,
) -> QAResult:
    """Generate an answer from question and retrieved ontology facts.

    Args:
        question: User question.
        context_snippets: Retrieved fact strings (from graph_index retrieval).
        source_refs: Parallel list of source reference IDs for attribution.
            If None, uses fact:0, fact:1, ...
        ontological_context: OntoRAG-style taxonomy context (parents, children, defs).
        answer_language: ISO 639-1 code for answer language (e.g. en, fr). If None,
            the model is instructed to answer in the same language as the question.

    Returns:
        QAResult with answer text, sources, ontological_context, num_facts_used.
    """
    if source_refs is None:
        source_refs = [f"fact:{i}" for i in range(len(context_snippets))]

    # Use numeric refs in context so the LLM does not see node:/edge:/dp: and echo them
    annotated_facts = []
    for i, (fact, ref) in enumerate(zip(context_snippets, source_refs), start=1):
        annotated_facts.append(f"[{i}] {fact}")

    context = "\n".join(annotated_facts)
    max_context_chars = get_settings().qa_max_context_chars
    if len(context) > max_context_chars:
        logger.debug("[QA] Truncating context from %d to %d chars", len(context), max_context_chars)
        context = context[:max_context_chars] + "\n[... truncated ...]"

    if agent_mode:
        user = build_agent_qa_user_prompt(
            context, question, ontological_context, answer_language=answer_language
        )
        system = AGENT_QA_SYSTEM
        max_tokens = 3000
    else:
        user = build_qa_user_prompt(
            context, question, ontological_context, answer_language=answer_language
        )
        system = QA_SYSTEM
        max_tokens = 2000

    response_text = complete(
        system=system,
        user=user,
        temperature=0.2,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    logger.info("[QA] Response generated | length=%d chars | facts=%d", len(response_text), len(context_snippets))

    # Parse JSON; fallback to plain text if parsing fails
    reasoning = ""
    answer_text = response_text
    try:
        parsed = json.loads(response_text)
        reasoning = (parsed.get("reasoning") or "").strip()
        answer_text = (parsed.get("answer") or answer_text).strip()
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("[QA] JSON parse failed, using raw response as answer: %s", e)
        answer_text = response_text.strip()

    # Strip any raw source IDs the LLM may have echoed (safety net)
    reasoning = _RAW_ID_PATTERN.sub(" ", reasoning)
    reasoning = re.sub(r"[ \t]+", " ", reasoning).strip()
    reasoning = re.sub(r"\n\s*\n\s*\n+", "\n\n", reasoning)
    answer_text = _RAW_ID_PATTERN.sub(" ", answer_text)
    answer_text = re.sub(r"[ \t]+", " ", answer_text).strip()
    answer_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", answer_text)

    return QAResult(
        answer=answer_text,
        reasoning=reasoning,
        sources=source_refs[:len(context_snippets)],
        ontological_context=ontological_context,
        num_facts_used=len(context_snippets),
    )


QA_SYSTEM_EVAL = """\
You answer questions using ONLY the provided ontology facts. Your answer is evaluated for faithfulness (context support) and relevancy (addressing the question).

Rules:
- Base your answer STRICTLY on the retrieved facts. You may use natural language or ontology terms (e.g. "battle power" or "CombatPower" — both are fine).
- Directly address the question. Be concise: 2-4 sentences in plain prose (no bullet points, headers, or "Based on the ontology..." caveats).
- Do NOT invent, infer beyond the facts, or add external knowledge.
- Respond with valid JSON: {"reasoning": "...", "answer": "..."}. The answer field is what is scored."""


def answer_questions_batch(
    items: list[tuple[str, list[str], list[str], str]],
    system_prompt: str | None = None,
) -> list[QAResult]:
    """Answer multiple questions in parallel. Each item is (question, context_snippets, source_refs, onto_ctx).
    Use system_prompt=QA_SYSTEM_EVAL for evaluation (stricter faithfulness/relevancy).
    """
    if not items:
        return []

    prompt = system_prompt or QA_SYSTEM

    def system_fn(_: tuple) -> str:
        return prompt

    def user_fn(item: tuple[str, list[str], list[str], str]) -> str:
        question, context_snippets, source_refs, onto_ctx = item
        source_refs = source_refs or [f"fact:{i}" for i in range(len(context_snippets))]
        annotated_facts = [f"[{i}] {fact}" for i, (fact, ref) in enumerate(zip(context_snippets, source_refs), start=1)]
        context = "\n".join(annotated_facts)
        max_context_chars = get_settings().qa_max_context_chars
        if len(context) > max_context_chars:
            context = context[:max_context_chars] + "\n[... truncated ...]"
        return build_qa_user_prompt(context, question, onto_ctx)

    responses = complete_batch(
        items,
        system_fn=system_fn,
        user_fn=user_fn,
        temperature=0.2,
        response_format={"type": "json_object"},
        max_tokens=2000,
    )

    results: list[QAResult] = []
    for i, (question, context_snippets, source_refs, onto_ctx) in enumerate(items):
        response_text = responses[i] if i < len(responses) else ""
        answer_text = _parse_answer_from_response(response_text)
        answer_text = _RAW_ID_PATTERN.sub(" ", answer_text)
        answer_text = re.sub(r"[ \t]+", " ", answer_text).strip()
        answer_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", answer_text)
        results.append(QAResult(
            answer=answer_text,
            reasoning="",
            sources=source_refs[:len(context_snippets)] if source_refs else [],
            ontological_context=onto_ctx,
            num_facts_used=len(context_snippets),
        ))
    return results
