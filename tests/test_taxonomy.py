"""Tests for taxonomy builder."""

import json

import pytest

from ontology_builder.ontology.schema import OntologyClass
from ontology_builder.pipeline.taxonomy_builder import (
    _deduplicate_classes,
    _grounding_check,
    build_taxonomy,
)


def test_deduplicate_classes():
    classes = [
        OntologyClass(name="Animal", description="short"),
        OntologyClass(name="animal", description="A living organism that moves"),
        OntologyClass(name="Plant", description="Photosynthetic organism"),
    ]
    result = _deduplicate_classes(classes)
    names = {c.name.lower() for c in result}
    assert len(result) == 2
    assert "animal" in names
    assert "plant" in names


def test_grounding_check_exact_match():
    classes = [
        {"name": "Neural Network"},
        {"name": "Quantum Entanglement"},
    ]
    source = "Neural networks are used in machine learning."
    result = _grounding_check(classes, source)
    assert len(result) == 1
    assert result[0]["name"] == "Neural Network"


def test_grounding_check_token_match():
    classes = [
        {"name": "Machine Learning"},
    ]
    source = "We use machine algorithms for learning tasks."
    result = _grounding_check(classes, source)
    assert len(result) == 1


def test_grounding_check_empty_source():
    classes = [{"name": "Anything"}]
    result = _grounding_check(classes, "")
    assert len(result) == 1


def test_build_taxonomy_single_class():
    classes = [OntologyClass(name="Thing")]
    result = build_taxonomy(classes)
    assert len(result) == 1
    assert result[0].name == "Thing"


def test_build_taxonomy_organizes_hierarchy(monkeypatch):
    """Taxonomy builder organizes classes via LLM into hierarchy."""
    from ontology_builder.pipeline import taxonomy_builder

    def mock_llm(system, user, temperature=0.1):
        return json.dumps({
            "taxonomy": [
                {"name": "Animal", "parent": None, "description": "Living creature"},
                {"name": "Dog", "parent": "Animal", "description": "Domestic canine"},
                {"name": "Cat", "parent": "Animal", "description": "Domestic feline"},
            ]
        })

    monkeypatch.setattr(taxonomy_builder, "complete", mock_llm)

    classes = [
        OntologyClass(name="Animal", description="Living creature"),
        OntologyClass(name="Dog", description="Domestic canine"),
        OntologyClass(name="Cat", description="Domestic feline"),
    ]
    result = build_taxonomy(classes, source_text="Animals include dogs and cats.")
    name_to_cls = {c.name: c for c in result}
    assert name_to_cls["Dog"].parent == "Animal"
    assert name_to_cls["Cat"].parent == "Animal"
    assert name_to_cls["Animal"].parent is None
