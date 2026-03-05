"""Pydantic models for ontology extraction: Entity, Relation, OntologyExtraction."""

from pydantic import BaseModel
from typing import List


class Entity(BaseModel):
    """Extracted entity with name, type, and description."""

    name: str
    type: str
    description: str


class Relation(BaseModel):
    """Extracted relation between two entities with confidence score."""

    source: str
    relation: str
    target: str
    confidence: float


class OntologyExtraction(BaseModel):
    """LLM extraction output: list of entities and relations."""

    entities: List[Entity]
    relations: List[Relation]
