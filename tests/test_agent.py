"""Tests for the advanced knowledge agent."""

from __future__ import annotations

import pytest

from ontology_builder.agent.concept_extractor import extract_concepts
from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.agent.ontology_gap_detector import detect_gaps
from ontology_builder.agent.reasoning_logger import load_reasoning_log, get_reasoning_logs_dir


def test_extract_concepts_fallback():
    """Fallback extraction works when LLM is not called."""
    # Fallback uses tokenization - we can test the structure
    result = extract_concepts("What should I build on Ezreal?")
    assert isinstance(result, list)
    assert all(isinstance(c, str) for c in result)
    # Fallback should extract some tokens
    assert len(result) >= 1


def test_reasoning_graph():
    """ReasoningGraph stores nodes and edges."""
    g = ReasoningGraph(initial_concepts=["ezreal", "champion"])
    assert len(g.nodes) == 2
    assert "ezreal" in g.nodes
    assert "champion" in g.nodes

    g.update(
        concepts=["item", "damage"],
        relations=[("ezreal", "benefits_from", "damage"), ("item", "increases", "damage")],
    )
    assert len(g.nodes) >= 4
    assert len(g.edges) == 2
    assert g.step_count == 1

    ctx = g.to_context_string()
    assert "ezreal" in ctx
    assert "damage" in ctx


def test_reasoning_graph_complete():
    """ReasoningGraph complete() stops at max steps."""
    g = ReasoningGraph(initial_concepts=["a"], max_steps=2)
    assert not g.complete()
    g.update(concepts=["b"], relations=[])
    assert not g.complete()
    g.update(concepts=[], relations=[])
    assert g.complete()


def test_detect_gaps():
    """Gap detector finds concepts without definitions."""
    g = ReasoningGraph(initial_concepts=["x", "y"])
    g.nodes["x"].definition = "X is a thing"
    # y has no definition
    gaps = detect_gaps("What is y?", g)
    assert any(gg.gap_type == "missing_concept" and gg.subject == "y" for gg in gaps)


def test_reasoning_logger_dir():
    """Reasoning logs dir exists or can be created."""
    path = get_reasoning_logs_dir()
    assert path is not None
    assert path.name == "reasoning_logs"


def test_load_reasoning_log_nonexistent():
    """Loading nonexistent log returns None."""
    assert load_reasoning_log("nonexistent-session-id-12345") is None
