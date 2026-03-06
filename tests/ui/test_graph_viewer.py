"""Unit tests for graph viewer: _edge_id, _build_vis_data, generate_visjs_html."""

from ontology_builder.storage.graphdb import OntologyGraph
from ontology_builder.ui.graph_viewer import (
    _build_vis_data,
    _edge_id,
    generate_visjs_html,
)


def test_edge_id_stable():
    """Same inputs always produce same id."""
    assert _edge_id("A", "B", "subClassOf") == _edge_id("A", "B", "subClassOf")


def test_edge_id_unique():
    """Different edges produce different ids."""
    assert _edge_id("A", "B", "x") != _edge_id("B", "A", "x")
    assert _edge_id("A", "B", "subClassOf") != _edge_id("A", "B", "type")


def test_build_vis_data_empty_graph():
    """Empty graph returns empty nodes/edges, no crash."""
    g = OntologyGraph()
    data = _build_vis_data(g)
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["edge_attrs"] == {}
    assert "stats_html" in data


def test_build_vis_data_edge_attrs_keyed_correctly():
    """edge_attrs keys match vis_edge ids 1:1."""
    g = OntologyGraph()
    g.add_class("A")
    g.add_class("B")
    g.add_relation("A", "subClassOf", "B")
    data = _build_vis_data(g)
    edge_ids = {e["id"] for e in data["edges"]}
    attrs_keys = set(data["edge_attrs"])
    assert edge_ids == attrs_keys, "edge_attrs keys should match vis edge ids"


def test_generate_visjs_html_valid_html():
    """Output parses as HTML without syntax errors."""
    g = OntologyGraph()
    g.add_class("X")
    html = generate_visjs_html(g)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "</html>" in html
    assert "vis.DataSet" in html
    # No unescaped {{ or }} that would break JS
    assert "var nodes = new vis.DataSet(" in html


def test_generate_visjs_html_pre_select_node():
    """pre_select_node value appears in output JS."""
    g = OntologyGraph()
    g.add_class("Foo")
    html = generate_visjs_html(g, pre_select_node="Foo")
    assert "preSelectNode" in html
    assert "Foo" in html
