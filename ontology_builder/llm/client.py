"""Unified LLM client with retries and parallel processing. Works with LM Studio and OpenAI."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

from openai import OpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings

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


def _should_retry(e: BaseException) -> bool:
    """Skip retry on context overflow (retrying won't help)."""
    err_str = str(e).lower()
    return "context size" not in err_str and "context length" not in err_str


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
    Retries use tenacity with exponential backoff; context overflow aborts immediately.
    """
    settings = get_settings()
    max_retries = settings.llm_max_retries

    @retry(
        stop=stop_after_attempt(max_retries + 1),
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
        before_sleep=lambda rs: logger.warning("[LLM] Retrying | attempt=%d", rs.attempt_number),
    )
    def _do_complete() -> str:
        logger.debug(
            "[LLM] Attempt | model=%s | user_len=%d | system_len=%d",
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
        raw = message.content if message else None
        if raw is None:
            return ""
        # Handle content as list (e.g. content blocks from some APIs)
        if isinstance(raw, list):
            parts = [p.get("text", p) if isinstance(p, dict) else str(p) for p in raw]
            content = "".join(str(p) for p in parts if p).strip()
        else:
            content = (raw or "").strip()
        return content

    try:
        return _do_complete()
    except Exception as e:
        if not _should_retry(e):
            logger.warning("[LLM] Context overflow — aborting immediately")
        raise RuntimeError(f"LLM request failed: {e}") from e


def complete_batch(
    items: list[T],
    system_fn: Callable[[T], str],
    user_fn: Callable[[T], str],
    temperature: float = 0.1,
    max_workers: int | None = None,
    parallel: bool = True,
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
) -> list[str]:
    """Process items via LLM completion. Returns results in order.

    Args:
        items: Items to process.
        system_fn: Function to get system prompt from item.
        user_fn: Function to get user message from item.
        temperature: Sampling temperature.
        max_workers: Thread pool size when parallel=True (default from config).
        parallel: If True, process items concurrently; if False, process sequentially.
        response_format: Optional JSON/text format for responses.
        max_tokens: Optional max tokens per completion.

    Returns:
        List of completion strings in same order as items.
    """
    if not items:
        return []

    def process_one(item: T) -> str:
        return complete(
            system=system_fn(item),
            user=user_fn(item),
            temperature=temperature,
            response_format=response_format,
            max_tokens=max_tokens,
        )

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
