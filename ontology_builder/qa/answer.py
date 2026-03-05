"""Generate answers from retrieved ontology facts with fact-level attribution.

Supports both simple (list[str]) and structured (RetrievalResult) context.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

from app.config import get_settings
from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.qa.prompts import QA_SYSTEM, build_qa_user_prompt

logger = logging.getLogger(__name__)

# Regex to strip raw source IDs ([node:X], [edge:A-R-B], [dp:E-A]) if LLM echoes them
_RAW_ID_PATTERN = re.compile(r"\s*\[(?:node|edge|dp):[^\]]+\]\s*", re.IGNORECASE)


@dataclass
class QAResult:
    """Structured QA answer with source attribution."""

    answer: str = ""
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
) -> QAResult:
    """Generate an answer from question and retrieved ontology facts.

    Args:
        question: User question.
        context_snippets: Retrieved fact strings (from graph_index retrieval).
        source_refs: Parallel list of source reference IDs for attribution.
            If None, uses fact:0, fact:1, ...
        ontological_context: OntoRAG-style taxonomy context (parents, children, defs).

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

    user = build_qa_user_prompt(context, question, ontological_context)
    answer_text = call_llm(system=QA_SYSTEM, user=user, temperature=0.2, max_tokens=1400)
    logger.info("[QA] Answer generated | length=%d chars | facts=%d", len(answer_text), len(context_snippets))

    # Strip any raw source IDs the LLM may have echoed (safety net)
    answer_text = _RAW_ID_PATTERN.sub(" ", answer_text)
    answer_text = re.sub(r"[ \t]+", " ", answer_text).strip()
    answer_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", answer_text)  # at most one blank line

    return QAResult(
        answer=answer_text,
        sources=source_refs[:len(context_snippets)],
        ontological_context=ontological_context,
        num_facts_used=len(context_snippets),
    )
