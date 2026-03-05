"""Unified LLM client with retries and parallel processing. Works with LM Studio and OpenAI."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")
_client: OpenAI | None = None
_client_lock = threading.Lock()


def _create_client() -> OpenAI:
    """Create OpenAI client from settings (works for LM Studio and OpenAI cloud)."""
    global _client
    with _client_lock:
        if _client is None:
            settings = get_settings()
            api_key = settings.get_llm_api_key()
            base_url = (settings.openai_base_url or "").lower()
            # OpenAI cloud requires a valid API key
            if "api.openai.com" in base_url and not (api_key and api_key.strip()):
                raise ValueError(
                    "OPENAI_API_KEY is required when using OpenAI cloud (api.openai.com). "
                    "Set OPENAI_API_KEY=sk-... in .env or environment."
                )
            _client = OpenAI(
                api_key=api_key,
                base_url=settings.openai_base_url,
            )
        return _client


def complete(
    system: str,
    user: str,
    temperature: float = 0.1,
    response_format: dict[str, Any] | None = None,
    force_text_mode: bool | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call configured LLM with retries. Single completion.

    Uses OpenAI-compatible /v1/chat/completions for both LM Studio and OpenAI cloud.

    Args:
        system: System prompt.
        user: User message.
        temperature: Sampling temperature (default 0.1).
        response_format: Optional OpenAI-compatible response_format payload
            (e.g. json_schema) for structured output.
        force_text_mode: Optional override for text mode behavior. If None,
            uses settings.llm_force_text_mode.
        max_tokens: Optional output token cap for faster bounded responses.

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
            kwargs = dict(
                model=settings.ontology_llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                timeout=settings.llm_timeout_seconds,
            )
            if max_tokens is not None and max_tokens > 0:
                kwargs["max_tokens"] = max_tokens
            if response_format is not None:
                # Structured output takes priority over text-mode forcing.
                kwargs["response_format"] = response_format
            else:
                should_force_text = (
                    getattr(settings, "llm_force_text_mode", True)
                    if force_text_mode is None
                    else force_text_mode
                )
                if should_force_text:
                    kwargs["response_format"] = {"type": "text"}
            response = client.chat.completions.create(**kwargs)
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
            err_str = str(e).lower()
            logger.warning("[LLM] Attempt %d failed | error=%s", attempt + 1, e)
            if "context size" in err_str or "context length" in err_str:
                logger.warning("[LLM] Context overflow — retrying won't help, aborting immediately")
                break
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
    parallel: bool = True,
) -> list[str]:
    """Process items via LLM completion. Returns results in order.

    Args:
        items: Items to process.
        system_fn: Function to get system prompt from item.
        user_fn: Function to get user message from item.
        temperature: Sampling temperature.
        max_workers: Thread pool size when parallel=True (default from config).
        parallel: If True, process items concurrently; if False, process sequentially.

    Returns:
        List of completion strings in same order as items.
    """
    if not items:
        return []

    def process_one(item: T) -> str:
        return complete(system=system_fn(item), user=user_fn(item), temperature=temperature)

    if not parallel:
        results: list[str] = []
        for item in items:
            try:
                results.append(process_one(item))
            except Exception as e:
                logger.warning("[LLM] Batch item failed | error=%s", e)
                results.append("")
        return results

    settings = get_settings()
    workers = max_workers if max_workers is not None else settings.get_llm_parallel_workers()

    results_tuples: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_one, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                content = future.result()
                results_tuples.append((idx, content))
            except Exception as e:
                logger.warning("[LLM] Batch item %d failed | error=%s", idx, e)
                results_tuples.append((idx, ""))

    results_tuples.sort(key=lambda x: x[0])
    return [r[1] for r in results_tuples]
