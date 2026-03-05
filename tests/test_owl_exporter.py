"""Tests for OWL/RDF ontology export."""

import pytest

from ontology_builder.export.owl_exporter import export_ontology_to_rdf, ontology_graph_to_rdflib
from ontology_builder.storage.graphdb import OntologyGraph


def test_export_turtle():
    """Export to Turtle format produces valid RDF."""
    g = OntologyGraph()
    g.add_class("Animal", "Living organism")
    g.add_class("Dog", "Domestic canine", parent="Animal")
    g.add_instance("Rex", "Dog", "A friendly dog")
    g.add_relation("Rex", "hasOwner", "Alice")
    g.add_data_property("Rex", "age", "5", "integer")

    out = export_ontology_to_rdf(g, format="turtle")
    assert isinstance(out, str)
    assert "@prefix" in out
    assert "owl:Class" in out
    assert "Animal" in out or "Dog" in out
    assert "Rex" in out


def test_export_json_ld():
    """Export to JSON-LD format produces valid output."""
    g = OntologyGraph()
    g.add_class("Concept", "Abstract idea")

    out = export_ontology_to_rdf(g, format="json-ld")
    assert isinstance(out, str)
    assert "@context" in out or '"@context"' in out


def test_export_xml():
    """Export to RDF/XML format produces valid output."""
    g = OntologyGraph()
    g.add_class("Thing", "Base concept")

    out = export_ontology_to_rdf(g, format="xml")
    assert isinstance(out, (str, bytes))
    content = out.decode("utf-8") if isinstance(out, bytes) else out
    assert "rdf:RDF" in content or "rdf:" in content


def test_export_axioms():
    """Axioms (disjointness, etc.) are exported."""
    g = OntologyGraph()
    g.add_class("Cat", "")
    g.add_class("Dog", "")
    g.add_axiom({"axiom_type": "disjointness", "entities": ["Cat", "Dog"]})

    out = export_ontology_to_rdf(g, format="turtle")
    assert "disjointWith" in out or "owl:disjointWith" in out


def test_export_invalid_format():
    """Unsupported format raises ValueError."""
    g = OntologyGraph()
    with pytest.raises(ValueError, match="Unsupported format"):
        export_ontology_to_rdf(g, format="invalid")


def test_ontology_graph_to_rdflib():
    """Conversion produces rdflib Graph with triples."""
    g = OntologyGraph()
    g.add_class("TestClass", "Test description")

    rdf = ontology_graph_to_rdflib(g)
    assert len(rdf) > 0
    assert rdf is not None
