"""
Generate an answer to a question using retrieved ontology snippets and the LLM.
"""
import logging

from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.qa.prompts import QA_SYSTEM, build_qa_user_prompt

logger = logging.getLogger(__name__)

# Limit context size to keep latency and cost low (chars)
MAX_CONTEXT_CHARS = 4000


def answer_question(question: str, context_snippets: list[str]) -> str:
    """Generate answer from question and retrieved ontology snippets.

    Args:
        question: User question.
        context_snippets: Retrieved facts (subject, attribute, value format).

    Returns:
        LLM-generated answer string.
    """
    logger.debug("[QAAnswer] Generating answer | snippets=%d | question_len=%d", len(context_snippets), len(question))
    context = "\n".join(context_snippets)
    if len(context) > MAX_CONTEXT_CHARS:
        logger.debug("[QAAnswer] Truncating context from %d to %d chars", len(context), MAX_CONTEXT_CHARS)
        context = context[:MAX_CONTEXT_CHARS] + "\n[... truncated ...]"
    user = build_qa_user_prompt(context, question)
    answer = call_llm(system=QA_SYSTEM, user=user, temperature=0.2)
    logger.info("[QAAnswer] Answer generated | length=%d chars", len(answer))
    return answer
