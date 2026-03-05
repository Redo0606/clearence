"""Tests for unified LLM client (retries, batch)."""

import pytest

from ontology_builder.llm.client import complete, complete_batch


def test_complete_retries_then_raises(monkeypatch):
    """Verify complete retries then raises RuntimeError after all attempts fail."""
    call_count = 0

    def mock_chat_create(**kwargs):
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Persistent failure")

    def mock_client():
        return type("Client", (), {"chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": staticmethod(mock_chat_create),
            })()
        })()})()

    monkeypatch.setattr("ontology_builder.llm.client._create_client", mock_client)
    monkeypatch.setattr("ontology_builder.llm.client.get_settings", lambda: type("S", (), {
        "llm_max_retries": 2,
        "llm_timeout_seconds": 60,
        "ontology_llm_model": "test",
        "openai_base_url": "https://api.example.com/v1",
        "get_llm_api_key": lambda: "test-key",
    })())
    monkeypatch.setattr("ontology_builder.llm.client.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        complete(system="sys", user="user")
    assert call_count == 3


def test_complete_sends_explicit_response_format(monkeypatch):
    """Explicit response_format should be forwarded to chat completions."""
    seen = {}

    class _Message:
        content = '{"ok": true}'

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]
        usage = None

    def mock_chat_create(**kwargs):
        seen.update(kwargs)
        return _Response()

    def mock_client():
        return type("Client", (), {"chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": staticmethod(mock_chat_create),
            })()
        })()})()

    monkeypatch.setattr("ontology_builder.llm.client._create_client", mock_client)
    monkeypatch.setattr("ontology_builder.llm.client.get_settings", lambda: type("S", (), {
        "llm_max_retries": 0,
        "llm_timeout_seconds": 60,
        "ontology_llm_model": "test",
        "llm_force_text_mode": True,
    })())

    schema = {"type": "json_schema", "json_schema": {"name": "x", "schema": {"type": "object"}}}
    complete(system="sys", user="user", response_format=schema)

    assert seen["response_format"] == schema


def test_complete_batch_returns_in_order(monkeypatch):
    """Verify complete_batch returns results in same order as items."""
    def fake_complete(system, user, temperature=0.1):
        # Return the user content reversed as a simple ordering test
        return user[-1] if user else ""

    monkeypatch.setattr("ontology_builder.llm.client.complete", fake_complete)

    items = ["a", "bb", "ccc"]
    results = complete_batch(
        items,
        system_fn=lambda x: "sys",
        user_fn=lambda x: x,
        max_workers=2,
    )
    assert len(results) == 3
    assert results[0] == "a"
    assert results[1] == "b"
    assert results[2] == "c"
