"""Tests for sequential extractor (mocked LLM calls)."""

import json

import pytest

from ontology_builder.pipeline.extractor import (
    _strip_fences,
    extract_ontology,
    extract_ontology_sequential,
)


def test_strip_fences_json():
    raw = '```json\n{"key": "value"}\n```'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_plain():
    raw = '{"key": "value"}'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_empty():
    assert _strip_fences("") == ""


def test_extract_ontology_legacy_mock(monkeypatch):
    """Legacy single-shot extraction returns entities and relations."""
    response = json.dumps({
        "entities": [{"name": "A", "type": "T", "description": "d"}],
        "relations": [{"source": "A", "relation": "r", "target": "B", "confidence": 0.8}],
    })

    from ontology_builder.pipeline import extractor
    monkeypatch.setattr(
        extractor,
        "complete",
        lambda system, user, temperature=0.1, response_format=None, force_text_mode=None: response,
    )

    result = extract_ontology("Some text")
    assert len(result["entities"]) == 1
    assert result["entities"][0]["name"] == "A"
    assert len(result["relations"]) == 1


def test_extract_ontology_sequential_mock(monkeypatch):
    """Sequential extraction returns structured OntologyExtraction."""
    call_count = 0

    def mock_llm(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return json.dumps({
                "classes": [{"name": "Vehicle", "parent": None, "description": "A means of transport"}]
            })
        elif call_count == 2:
            return json.dumps({
                "instances": [{"name": "Tesla Model 3", "class_name": "Vehicle", "description": "Electric car"}]
            })
        else:
            return json.dumps({
                "object_properties": [
                    {"source": "Tesla Model 3", "relation": "manufactured_by", "target": "Tesla",
                     "confidence": 0.9, "symmetric": False, "transitive": False}
                ],
                "data_properties": [],
                "axioms": [],
            })

    from ontology_builder.pipeline import extractor
    monkeypatch.setattr(extractor, "complete", mock_llm)

    result = extract_ontology_sequential("Text about vehicles")
    assert len(result.classes) == 1
    assert result.classes[0].name == "Vehicle"
    assert len(result.instances) == 1
    assert result.instances[0].class_name == "Vehicle"
    assert len(result.object_properties) == 1
    assert result.object_properties[0].relation == "manufactured_by"
    assert call_count == 3


def test_extract_ontology_sequential_llm_failure(monkeypatch):
    """Sequential extraction gracefully handles LLM failure."""
    from ontology_builder.pipeline import extractor
    monkeypatch.setattr(extractor, "complete", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("LLM down")))

    result = extract_ontology_sequential("Text")
    assert len(result.classes) == 0
    assert len(result.instances) == 0
    assert len(result.object_properties) == 0


def test_extract_ontology_sends_json_schema_response_format(monkeypatch):
    """Legacy extraction should request structured JSON schema output."""
    from ontology_builder.pipeline import extractor

    seen = {}
    response = json.dumps({"entities": [], "relations": []})

    def mock_llm(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        seen["response_format"] = response_format
        seen["force_text_mode"] = force_text_mode
        return response

    monkeypatch.setattr(extractor, "complete", mock_llm)
    extract_ontology("Some text")

    assert seen["response_format"]["type"] == "json_schema"
    assert "json_schema" in seen["response_format"]
    assert seen["force_text_mode"] is None


def test_extract_ontology_falls_back_to_text_mode_once(monkeypatch):
    """On structured output errors, extractor retries once with force_text_mode=True."""
    from ontology_builder.pipeline import extractor

    calls = {"count": 0, "second_force_text_mode": None}
    response = json.dumps({"entities": [], "relations": []})

    def mock_llm(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Invalid JSON Schema: Unrecognized schema")
        calls["second_force_text_mode"] = force_text_mode
        return response

    monkeypatch.setattr(extractor, "complete", mock_llm)
    result = extract_ontology("Some text")

    assert calls["count"] == 2
    assert calls["second_force_text_mode"] is True
    assert result == {"entities": [], "relations": []}
