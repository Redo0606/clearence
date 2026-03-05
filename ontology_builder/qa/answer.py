"""Generate answers from retrieved ontology facts with fact-level attribution.

Supports both simple (list[str]) and structured (RetrievalResult) context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.qa.prompts import QA_SYSTEM, build_qa_user_prompt

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 4000


@dataclass
class QAResult:
    """Structured QA answer with source attribution."""

    answer: str = ""
    sources: list[str] = field(default_factory=list)
    ontological_context: str = ""
    num_facts_used: int = 0


def answer_question(
    question: str,
    context_snippets: list[str],
    source_refs: list[str] | None = None,
    ontological_context: str = "",
) -> QAResult:
    """Generate an answer from question and retrieved ontology facts.

    Args:
        question: User question.
        context_snippets: Retrieved fact strings.
        source_refs: Parallel list of source reference IDs for attribution.
        ontological_context: OntoRAG-style taxonomy context string.

    Returns:
        QAResult with answer, sources, and context metadata.
    """
    if source_refs is None:
        source_refs = [f"fact:{i}" for i in range(len(context_snippets))]

    annotated_facts = []
    for fact, ref in zip(context_snippets, source_refs):
        annotated_facts.append(f"[{ref}] {fact}")

    context = "\n".join(annotated_facts)
    if len(context) > MAX_CONTEXT_CHARS:
        logger.debug("[QA] Truncating context from %d to %d chars", len(context), MAX_CONTEXT_CHARS)
        context = context[:MAX_CONTEXT_CHARS] + "\n[... truncated ...]"

    user = build_qa_user_prompt(context, question, ontological_context)
    answer_text = call_llm(system=QA_SYSTEM, user=user, temperature=0.2)
    logger.info("[QA] Answer generated | length=%d chars | facts=%d", len(answer_text), len(context_snippets))

    return QAResult(
        answer=answer_text,
        sources=source_refs[:len(context_snippets)],
        ontological_context=ontological_context,
        num_facts_used=len(context_snippets),
    )
