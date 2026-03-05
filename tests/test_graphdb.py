"""Tests for upgraded OntologyGraph with class/instance nodes, axioms, and factual blocks."""

from ontology_builder.ontology.schema import (
    Axiom,
    AxiomType,
    DataProperty,
    ObjectProperty,
    OntologyClass,
    OntologyExtraction,
    OntologyInstance,
)
from ontology_builder.storage.graphdb import OntologyGraph


def test_add_class_and_instance():
    g = OntologyGraph()
    g.add_class("Animal", "A living creature")
    g.add_instance("Fido", "Animal", "A dog")
    assert "Animal" in g.get_classes()
    assert "Fido" in g.get_instances()
    assert g.has_edge("Fido", "Animal", "type")


def test_add_class_with_parent():
    g = OntologyGraph()
    g.add_class("Animal")
    g.add_class("Dog", parent="Animal")
    assert g.has_edge("Dog", "Animal", "subClassOf")
    assert g.get_parents("Dog") == ["Animal"]
    assert g.get_children("Animal") == ["Dog"]


def test_add_relation_structured_facts():
    g = OntologyGraph()
    g.add_entity("A", "Class", "class")
    g.add_entity("B", "Class", "class")
    g.add_relation("A", "partOf", "B")
    data = g.get_graph()["A"]["B"]
    assert data["key"] == "A: partOf"
    assert data["value"] == "B"
    assert "full" in data


def test_add_axiom():
    g = OntologyGraph()
    g.add_axiom({"axiom_type": "disjointness", "entities": ["Cat", "Dog"]})
    assert len(g.axioms) == 1
    assert g.axioms[0]["axiom_type"] == "disjointness"


def test_add_data_property():
    g = OntologyGraph()
    g.add_entity("Fido", "Dog", "instance")
    g.add_data_property("Fido", "age", "5", "integer")
    assert len(g.data_properties) == 1
    assert g.data_properties[0]["attribute"] == "age"


def test_to_factual_blocks():
    g = OntologyGraph()
    g.add_class("Animal")
    g.add_class("Dog", parent="Animal")
    g.add_instance("Fido", "Dog")
    g.add_data_property("Fido", "age", "5")

    blocks = g.to_factual_blocks()
    assert len(blocks) >= 2
    subjects = {b["subject"] for b in blocks}
    assert "Dog" in subjects


def test_merge_extraction():
    g = OntologyGraph()
    ext = OntologyExtraction(
        classes=[OntologyClass(name="Vehicle", description="Transport")],
        instances=[OntologyInstance(name="Tesla", class_name="Vehicle")],
        object_properties=[
            ObjectProperty(source="Tesla", relation="type", target="ElectricCar", confidence=0.9),
        ],
        axioms=[Axiom(axiom_type=AxiomType.TRANSITIVITY, entities=["partOf"])],
    )
    g.merge_extraction(ext)
    assert "Vehicle" in g.get_classes()
    assert "Tesla" in g.get_instances()
    assert len(g.axioms) == 1


def test_export_includes_stats():
    g = OntologyGraph()
    g.add_class("A")
    g.add_instance("x", "A")
    export = g.export()
    assert "stats" in export
    assert export["stats"]["classes"] == 1
    assert export["stats"]["instances"] == 1


def test_get_node_description():
    g = OntologyGraph()
    g.add_class("Animal", description="Living creature")
    assert g.get_node_description("Animal") == "Living creature"
    assert g.get_node_description("NonExistent") == ""
