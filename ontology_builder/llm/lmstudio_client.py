"""Thin wrapper for LLM calls. Delegates to unified client with retries."""

from ontology_builder.llm.client import complete


def call_llm(system: str, user: str, temperature: float = 0.1) -> str:
    """Call configured LLM (LM Studio or OpenAI-compatible API) with retries.

    Args:
        system: System prompt.
        user: User message.
        temperature: Sampling temperature (default 0.1).

    Returns:
        Assistant message content.

    Raises:
        RuntimeError: If response is empty or all retries fail.
    """
    return complete(system=system, user=user, temperature=temperature)
