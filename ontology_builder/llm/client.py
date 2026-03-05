"""Unified LLM client with retries and parallel processing. Works with LM Studio and OpenAI."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _create_client() -> OpenAI:
    """Create OpenAI client from settings (works for LM Studio and OpenAI cloud)."""
    settings = get_settings()
    return OpenAI(
        api_key=settings.get_llm_api_key(),
        base_url=settings.openai_base_url,
    )


def complete(system: str, user: str, temperature: float = 0.1) -> str:
    """Call configured LLM with retries. Single completion.

    Uses OpenAI-compatible /v1/chat/completions for both LM Studio and OpenAI cloud.
    (LM Studio native /api/v1/chat can fail with "Invalid JSON Schema" when the prompt
    contains JSON examples; the OpenAI-compatible endpoint avoids this.)

    Args:
        system: System prompt.
        user: User message.
        temperature: Sampling temperature (default 0.1).

    Returns:
        Assistant message content.

    Raises:
        RuntimeError: If all retries fail or response is empty.
    """
    settings = get_settings()
    max_retries = settings.llm_max_retries

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            logger.debug(
                "[LLM] Attempt %d/%d | model=%s | user_len=%d | system_len=%d",
                attempt + 1,
                max_retries + 1,
                settings.ontology_llm_model,
                len(user),
                len(system),
            )
            client = _create_client()
            response = client.chat.completions.create(
                model=settings.ontology_llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                timeout=settings.llm_timeout_seconds,
                extra_body={"response_format": {"type": "text"}},
            )
            usage = getattr(response, "usage", None) or {}
            logger.debug(
                "[LLM] Response received | prompt_tokens=%s | completion_tokens=%s",
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
            )
            choices = response.choices or []
            if not choices:
                raise RuntimeError("Empty LLM response")
            message = choices[0].message if choices else None
            content = (message.content or "").strip() if message else ""
            return content
        except Exception as e:
            last_error = e
            logger.warning("[LLM] Attempt %d failed | error=%s", attempt + 1, e)
            if attempt < max_retries:
                delay = 2**attempt  # 1s, 2s, 4s
                logger.debug("[LLM] Retrying in %ds", delay)
                time.sleep(delay)

    raise RuntimeError(f"LLM request failed after {max_retries + 1} attempts: {last_error}") from last_error


def complete_batch(
    items: list[T],
    system_fn: Callable[[T], str],
    user_fn: Callable[[T], str],
    temperature: float = 0.1,
    max_workers: int | None = None,
) -> list[str]:
    """Process items in parallel, each via a single LLM completion. Returns results in order.

    Args:
        items: Items to process.
        system_fn: Function to get system prompt from item.
        user_fn: Function to get user message from item.
        temperature: Sampling temperature.
        max_workers: Thread pool size (default from config).

    Returns:
        List of completion strings in same order as items.
    """
    if not items:
        return []

    settings = get_settings()
    workers = max_workers if max_workers is not None else settings.llm_parallel_workers

    def process_one(item: T) -> str:
        return complete(system=system_fn(item), user=user_fn(item), temperature=temperature)

    results: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_one, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                content = future.result()
                results.append((idx, content))
            except Exception as e:
                logger.warning("[LLM] Batch item %d failed | error=%s", idx, e)
                results.append((idx, ""))

    # Restore order
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]
