"""Pydantic models for ontology schema (classes, properties) and API request/response."""

from pydantic import BaseModel, Field


# LLM response schema: used by llm_extract and ontology builder
class ClassDef(BaseModel):
    """OWL class definition with optional parent for subclass hierarchy."""

    name: str = Field(..., description="Class name (PascalCase or similar)")
    parent: str | None = Field(None, description="Parent class name if subclass")


class ObjectProperty(BaseModel):
    """Object property linking two classes (domain and range)."""

    name: str = Field(..., description="Property name (camelCase)")
    domain: str = Field(..., description="Domain class name")
    range: str = Field(..., description="Range class name")


class DatatypeProperty(BaseModel):
    """Datatype property linking a class to a primitive type (string, int, etc.)."""

    name: str = Field(..., description="Property name (camelCase)")
    domain: str = Field(..., description="Domain class name")
    range: str = Field(..., description="Datatype: string, int, float, date, boolean, etc.")


class OntologySchema(BaseModel):
    """Full ontology schema: namespace, classes, object properties, datatype properties."""

    namespace_prefix: str = Field(default="field", description="Short prefix for ontology URI")
    namespace_uri: str = Field(default="http://example.org/field#", description="Base URI for the ontology")
    classes: list[ClassDef] = Field(default_factory=list, description="List of classes")
    object_properties: list[ObjectProperty] = Field(default_factory=list, description="Object properties")
    datatype_properties: list[DatatypeProperty] = Field(default_factory=list, description="Datatype properties")


# API request/response models
class OntologyFromPdfResponse(BaseModel):
    """Response for ontology/from-pdf when response_type=json."""

    namespace: str
    format: str
    class_count: int
    object_property_count: int
    datatype_property_count: int
    content: str | None = None  # When response_type=json
    filename: str | None = None  # When response_type=file
