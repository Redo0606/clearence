"""Thin wrapper for LLM calls. Delegates to unified client with retries."""

from typing import Any

from ontology_builder.llm.client import complete


def call_llm(
    system: str,
    user: str,
    temperature: float = 0.1,
    response_format: dict[str, Any] | None = None,
    force_text_mode: bool | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call configured LLM (LM Studio or OpenAI-compatible API) with retries.

    Args:
        system: System prompt.
        user: User message.
        temperature: Sampling temperature (default 0.1).
        response_format: Optional structured response_format payload.
        force_text_mode: Optional text-mode override.
        max_tokens: Optional output token cap.

    Returns:
        Assistant message content.

    Raises:
        RuntimeError: If response is empty or all retries fail.
    """
    return complete(
        system=system,
        user=user,
        temperature=temperature,
        response_format=response_format,
        force_text_mode=force_text_mode,
        max_tokens=max_tokens,
    )
