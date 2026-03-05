"""Tests for OWL 2 RL reasoning engine."""

from ontology_builder.reasoning.engine import (
    ReasoningResult,
    run_inference,
)
from ontology_builder.storage.graphdb import OntologyGraph


def _make_taxonomy_graph() -> OntologyGraph:
    """A -> B -> C taxonomy with instances."""
    g = OntologyGraph()
    g.add_class("C")
    g.add_class("B", parent="C")
    g.add_class("A", parent="B")
    g.add_instance("x", "A")
    return g


def test_transitive_subsumption():
    g = _make_taxonomy_graph()
    result = run_inference(g)
    assert isinstance(result, ReasoningResult)
    assert g.has_edge("A", "C", "subClassOf")
    assert result.inferred_edges > 0


def test_inheritance():
    g = _make_taxonomy_graph()
    result = run_inference(g)
    assert g.has_edge("x", "B", "type")
    assert g.has_edge("x", "C", "type")


def test_disjointness_violation():
    g = OntologyGraph()
    g.add_class("Cat")
    g.add_class("Dog")
    g.add_axiom({"axiom_type": "disjointness", "entities": ["Cat", "Dog"]})
    g.add_instance("x", "Cat")
    g.add_relation("x", "type", "Dog")
    result = run_inference(g)
    assert len(result.consistency_violations) >= 1
    assert "disjoint" in result.consistency_violations[0].lower()


def test_symmetric_closure():
    g = OntologyGraph()
    g.add_entity("A", "Class", "class")
    g.add_entity("B", "Class", "class")
    g.add_relation("A", "related_to", "B")
    result = run_inference(g)
    assert g.has_edge("B", "A", "related_to")


def test_fixpoint_terminates():
    g = OntologyGraph()
    g.add_class("Root")
    for i in range(5):
        g.add_class(f"L{i}", parent="Root" if i == 0 else f"L{i - 1}")
    result = run_inference(g)
    assert result.iterations <= 20
    assert g.has_edge("L4", "Root", "subClassOf")


def test_inference_trace_populated():
    g = _make_taxonomy_graph()
    result = run_inference(g)
    assert len(result.inference_trace) > 0
    first = result.inference_trace[0]
    assert "rule" in first
    assert "source" in first
    assert "relation" in first


def test_empty_graph_no_crash():
    g = OntologyGraph()
    result = run_inference(g)
    assert result.inferred_edges == 0
    assert result.iterations == 1
