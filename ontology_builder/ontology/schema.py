"""Formal ontology schema following Guarino's O = {C, R, I, P} and OntoRAG Def 2.1.

Provides structured Pydantic models that distinguish classes (concepts/universals),
instances (individuals/particulars), object properties (binary relations),
data properties (attribute-value pairs), and axioms (meaning postulates).

Every extracted element carries provenance (source document, chunk, confidence)
for reproducibility and explainability.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Relation taxonomy and canonical names
# ---------------------------------------------------------------------------

RELATION_TAXONOMY = {
    "taxonomic": ["subClassOf", "isA", "kindOf", "typeOf"],
    "compositional": ["hasPart", "partOf", "contains", "consistsOf"],
    "functional": ["hasAbility", "canPerform", "hasRole", "performs"],
    "causal": ["causes", "enables", "prevents", "requires"],
    "associative": ["relatedTo", "associatedWith", "usedIn", "appearsIn"],
}

CANONICAL_RELATION_NAMES: dict[str, str] = {
    "isa": "subClassOf",
    "kindof": "subClassOf",
    "typeof": "subClassOf",
    "subclassof": "subClassOf",
    "contains": "hasPart",
    "consistsof": "partOf",
    "partof": "partOf",
    "haspart": "hasPart",
    "canperform": "hasAbility",
    "hasrole": "hasAbility",
    "performs": "hasAbility",
    "hasability": "hasAbility",
    "causes": "causes",
    "enables": "enables",
    "prevents": "prevents",
    "requires": "requires",
    "relatedto": "relatedTo",
    "associatedwith": "relatedTo",
    "usedin": "relatedTo",
    "appearsin": "relatedTo",
}


def normalize_relation_name(relation: str) -> str:
    """Map relation to canonical name. Case-insensitive. Returns original if not found."""
    if not relation or not isinstance(relation, str):
        return relation
    key = relation.strip().lower()
    return CANONICAL_RELATION_NAMES.get(key, relation)


# ---------------------------------------------------------------------------
# Provenance mixin
# ---------------------------------------------------------------------------

class Provenance(BaseModel):
    """Tracks where an extraction came from."""

    source_document: str = ""
    source_chunk: str = ""
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Axiom types (Guarino meaning postulates O1-O5)
# ---------------------------------------------------------------------------

class AxiomType(str, Enum):
    DISJOINTNESS = "disjointness"
    SYMMETRY = "symmetry"
    TRANSITIVITY = "transitivity"
    ASYMMETRY = "asymmetry"
    INVERSE = "inverse"
    FUNCTIONAL = "functional"
    SUBCLASS = "subclass"


# ---------------------------------------------------------------------------
# Core ontology components
# ---------------------------------------------------------------------------

class OntologyClass(Provenance):
    """A concept / universal in the ontology (unary predicate)."""

    name: str
    parent: str | None = None
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    salience: float = 0.5  # 0.0 to 1.0, how central is this class to the domain
    domain_tags: list[str] = Field(default_factory=list)  # e.g. ["gameplay", "character"]


class OntologyInstance(Provenance):
    """An individual / particular, typed by a class."""

    name: str
    class_name: str = ""
    description: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)  # key-value data properties extracted inline


class ObjectProperty(Provenance):
    """Binary relation between two entities with optional semantic flags."""

    source: str
    relation: str
    target: str
    domain: str | None = None
    range: str | None = None
    symmetric: bool = False
    transitive: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = ""  # sentence(s) that support this relation
    relation_type: str = ""  # taxonomic | compositional | functional | causal | associative
    bidirectional: bool = False


class DataProperty(Provenance):
    """Attribute-value pair attached to an entity."""

    entity: str
    attribute: str = ""
    value: str = ""
    datatype: str = "string"


class Axiom(Provenance):
    """A meaning postulate / formal constraint (Guarino Examples 3.2 O1-O5)."""

    axiom_type: AxiomType
    entities: list[str] = Field(min_length=1)
    description: str = ""


# ---------------------------------------------------------------------------
# Full extraction output
# ---------------------------------------------------------------------------

class OntologyExtraction(BaseModel):
    """Complete extraction output following O = {C, R, I, P} + axioms.

    This replaces the flat Entity/Relation model and provides the formal
    structure needed for downstream reasoning and RAG.
    """

    classes: list[OntologyClass] = Field(default_factory=list)
    instances: list[OntologyInstance] = Field(default_factory=list)
    object_properties: list[ObjectProperty] = Field(default_factory=list)
    data_properties: list[DataProperty] = Field(default_factory=list)
    axioms: list[Axiom] = Field(default_factory=list)

    def entity_names(self) -> set[str]:
        """All unique entity names (classes + instances)."""
        names: set[str] = set()
        for c in self.classes:
            names.add(c.name)
        for i in self.instances:
            names.add(i.name)
        return names

    @classmethod
    def merge(cls, extractions: list["OntologyExtraction"]) -> "OntologyExtraction":
        """Merge multiple extractions into one (concatenate all lists). Used for batched graph update."""
        if not extractions:
            return cls()
        classes: list[OntologyClass] = []
        instances: list[OntologyInstance] = []
        object_properties: list[ObjectProperty] = []
        data_properties: list[DataProperty] = []
        axioms: list[Axiom] = []
        for ext in extractions:
            classes.extend(ext.classes)
            instances.extend(ext.instances)
            object_properties.extend(ext.object_properties)
            data_properties.extend(ext.data_properties)
            axioms.extend(ext.axioms)
        return cls(
            classes=classes,
            instances=instances,
            object_properties=object_properties,
            data_properties=data_properties,
            axioms=axioms,
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Convert to the legacy {entities, relations} format for backward compat."""
        entities = []
        for c in self.classes:
            entities.append({"name": c.name, "type": "Class", "description": c.description})
        for inst in self.instances:
            entities.append({"name": inst.name, "type": inst.class_name, "description": inst.description})
        relations = []
        for op in self.object_properties:
            relations.append({
                "source": op.source,
                "relation": op.relation,
                "target": op.target,
                "confidence": op.confidence,
            })
        for cls in self.classes:
            if cls.parent:
                relations.append({
                    "source": cls.name,
                    "relation": "subClassOf",
                    "target": cls.parent,
                    "confidence": cls.extraction_confidence,
                })
        return {"entities": entities, "relations": relations}


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    """Legacy entity model — use OntologyClass / OntologyInstance instead."""

    name: str
    type: str
    description: str


class Relation(BaseModel):
    """Legacy relation model — use ObjectProperty instead."""

    source: str
    relation: str
    target: str
    confidence: float
