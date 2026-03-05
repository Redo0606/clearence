"""Re-export complete as call_llm for backward compatibility.

Prefer using ontology_builder.llm.client.complete directly.
"""

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
    """Deprecated: use ontology_builder.llm.client.complete instead."""
    return complete(
        system=system,
        user=user,
        temperature=temperature,
        response_format=response_format,
        force_text_mode=force_text_mode,
        max_tokens=max_tokens,
    )
