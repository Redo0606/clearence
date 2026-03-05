"""Tests for formal ontology schema (O = {C, R, I, P})."""

from ontology_builder.ontology.schema import (
    Axiom,
    AxiomType,
    DataProperty,
    ObjectProperty,
    OntologyClass,
    OntologyExtraction,
    OntologyInstance,
)


def test_ontology_class_defaults():
    cls = OntologyClass(name="Animal")
    assert cls.name == "Animal"
    assert cls.parent is None
    assert cls.description == ""
    assert cls.extraction_confidence == 1.0


def test_ontology_class_with_parent():
    cls = OntologyClass(name="Dog", parent="Animal", description="Domestic canine")
    assert cls.parent == "Animal"


def test_ontology_instance():
    inst = OntologyInstance(name="Fido", class_name="Dog", description="A specific dog")
    assert inst.class_name == "Dog"


def test_object_property_flags():
    prop = ObjectProperty(
        source="A", relation="partOf", target="B",
        symmetric=False, transitive=True, confidence=0.95,
    )
    assert prop.transitive is True
    assert prop.symmetric is False
    assert prop.confidence == 0.95


def test_data_property():
    dp = DataProperty(entity="Dog", attribute="legs", value="4", datatype="integer")
    assert dp.datatype == "integer"


def test_axiom():
    ax = Axiom(axiom_type=AxiomType.DISJOINTNESS, entities=["Cat", "Dog"])
    assert ax.axiom_type == AxiomType.DISJOINTNESS
    assert len(ax.entities) == 2


def test_ontology_extraction_entity_names():
    ext = OntologyExtraction(
        classes=[OntologyClass(name="Animal"), OntologyClass(name="Plant")],
        instances=[OntologyInstance(name="Fido", class_name="Animal")],
    )
    names = ext.entity_names()
    assert names == {"Animal", "Plant", "Fido"}


def test_ontology_extraction_to_legacy_dict():
    ext = OntologyExtraction(
        classes=[
            OntologyClass(name="Animal", parent="LivingThing", description="An animal"),
        ],
        instances=[
            OntologyInstance(name="Fido", class_name="Dog", description="A dog"),
        ],
        object_properties=[
            ObjectProperty(source="Dog", relation="eats", target="Food", confidence=0.9),
        ],
    )
    legacy = ext.to_legacy_dict()
    assert len(legacy["entities"]) == 2
    assert legacy["entities"][0]["type"] == "Class"
    assert legacy["entities"][1]["type"] == "Dog"
    relations = legacy["relations"]
    assert any(r["relation"] == "eats" for r in relations)
    assert any(r["relation"] == "subClassOf" for r in relations)


def test_ontology_extraction_empty():
    ext = OntologyExtraction()
    assert ext.entity_names() == set()
    legacy = ext.to_legacy_dict()
    assert legacy == {"entities": [], "relations": []}
