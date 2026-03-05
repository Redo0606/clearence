import json
from pathlib import Path

import pytest

from ontology_builder.pipeline.chunker import chunk_text
from ontology_builder.pipeline.loader import load_document
from ontology_builder.pipeline.extractor import extract_ontology
from ontology_builder.pipeline.ontology_builder import update_graph
from ontology_builder.storage.graphdb import OntologyGraph


def test_chunker_returns_expected_number_of_chunks():
    text = "a" * 3000
    chunks = chunk_text(text, size=1200, overlap=200)
    assert len(chunks) >= 2
    assert all(len(c) <= 1200 for c in chunks)
    # With size=1200, overlap=200, first chunk 0-1200, second starts at 1000
    assert chunks[0][:100] == "a" * 100
    assert chunks[1][:100] == "a" * 100


def test_chunker_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text(" ", size=10) == []


def test_chunker_single_chunk():
    text = "short"
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0] == "short"


def test_loader_txt(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("Hello world\nLine two", encoding="utf-8")
    assert load_document(str(p)) == "Hello world\nLine two"


def test_loader_md(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nBody", encoding="utf-8")
    content = load_document(str(p))
    assert "Title" in content and "Body" in content


def test_loader_unsupported_format(tmp_path):
    p = tmp_path / "doc.xyz"
    p.write_text("x")
    with pytest.raises(ValueError, match="Unsupported format"):
        load_document(str(p))


def test_loader_file_not_found():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_document("/nonexistent/path/doc.txt")


def test_update_graph_adds_entities_and_relations():
    graph = OntologyGraph()
    extraction = {
        "entities": [
            {"name": "Neuron", "type": "Concept", "description": "Unit"},
            {"name": "Layer", "type": "Concept", "description": "Group"},
        ],
        "relations": [
            {"source": "Layer", "relation": "contains", "target": "Neuron", "confidence": 0.9},
        ],
    }
    update_graph(graph, extraction, verbose=False)
    assert graph.get_graph().number_of_nodes() == 2
    assert graph.get_graph().number_of_edges() == 1
    export = graph.export()
    assert "nodes" in export
    assert "links" in export


def test_extract_ontology_mock(monkeypatch):
    """Test that extract_ontology parses LLM response and returns entities/relations."""
    fixed_response = json.dumps({
        "entities": [{"name": "A", "type": "T", "description": "d"}],
        "relations": [{"source": "A", "relation": "r", "target": "B", "confidence": 0.8}],
    })

    def fake_call(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        return fixed_response

    from ontology_builder.pipeline import extractor
    monkeypatch.setattr(extractor, "call_llm", fake_call)
    result = extract_ontology("Some chunk text")
    assert len(result["entities"]) == 1
    assert result["entities"][0]["name"] == "A"
    assert len(result["relations"]) == 1
    assert result["relations"][0]["source"] == "A" and result["relations"][0]["target"] == "B"


def test_process_document_verbose_false(monkeypatch, tmp_path):
    """Test process_document runs with verbose=False (no tqdm)."""
    doc = tmp_path / "doc.txt"
    doc.write_text("Neural networks have layers. Each layer contains neurons.", encoding="utf-8")

    fixed_response = json.dumps({
        "entities": [{"name": "Layer", "type": "Concept", "description": "d"}, {"name": "Neuron", "type": "Concept", "description": "d"}],
        "relations": [{"source": "Layer", "relation": "contains", "target": "Neuron", "confidence": 0.9}],
    })

    def fake_call(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        return fixed_response

    from ontology_builder.pipeline import extractor
    monkeypatch.setattr(extractor, "call_llm", fake_call)

    from ontology_builder.pipeline.run_pipeline import process_document
    graph, report = process_document(str(doc), run_inference=False, verbose=False, sequential=False, run_reasoning=False)
    assert graph.get_graph().number_of_nodes() >= 2
    assert graph.get_graph().number_of_edges() >= 1
    assert report.total_chunks >= 1


def test_process_document_parallel_sequential_mode(monkeypatch, tmp_path):
    """Test process_document with parallel_extraction=True and sequential mode (Bakker B)."""
    doc = tmp_path / "doc.txt"
    doc.write_text(
        "Neural networks have layers. Each layer contains neurons. "
        "Deep learning uses multiple layers. Convolutional networks process images.",
        encoding="utf-8",
    )

    call_count = 0

    def fake_call(system, user, temperature=0.1, response_format=None, force_text_mode=None):
        nonlocal call_count
        call_count += 1
        if "classes" in (system + user).lower() or call_count % 3 == 1:
            return json.dumps({"classes": [{"name": "Layer", "parent": None, "description": "d"}, {"name": "Neuron", "parent": None, "description": "d"}]})
        if "instances" in (system + user).lower() or call_count % 3 == 2:
            return json.dumps({"instances": [{"name": "InputLayer", "class_name": "Layer", "description": "d"}]})
        return json.dumps({
            "object_properties": [{"source": "Layer", "relation": "contains", "target": "Neuron", "confidence": 0.9, "symmetric": False, "transitive": False}],
            "data_properties": [],
            "axioms": [],
        })

    from ontology_builder.pipeline import extractor
    from ontology_builder.pipeline import taxonomy_builder
    monkeypatch.setattr(extractor, "call_llm", fake_call)
    monkeypatch.setattr(
        taxonomy_builder,
        "call_llm",
        lambda *a, **kw: json.dumps({"taxonomy": [{"name": "Layer", "parent": None}, {"name": "Neuron", "parent": "Layer"}]}),
    )

    from ontology_builder.pipeline.run_pipeline import process_document
    graph, report = process_document(
        str(doc),
        run_inference=False,
        verbose=False,
        sequential=True,
        run_reasoning=False,
        parallel_extraction=True,
    )
    assert graph.get_graph().number_of_nodes() >= 2
    assert report.total_chunks >= 1
    assert report.extraction_mode == "parallel"
