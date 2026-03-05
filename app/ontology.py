"""Build rdflib Graph from OntologySchema and serialize to OWL, Turtle, or JSON-LD."""

import logging

from rdflib import Graph, Namespace, URIRef, Literal

logger = logging.getLogger(__name__)
from rdflib.namespace import OWL, RDF, RDFS, XSD

from app.schemas import OntologySchema

# Map datatype names from LLM output to XSD URIs
XSD_BY_NAME: dict[str, URIRef] = {
    "string": XSD.string,
    "int": XSD.integer,
    "integer": XSD.integer,
    "float": XSD.double,
    "double": XSD.double,
    "date": XSD.date,
    "datetime": XSD.dateTime,
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
}


def build_ontology(schema: OntologySchema) -> Graph:
    """Build an rdflib Graph (OWL ontology) from OntologySchema.

    Args:
        schema: Ontology schema with classes and properties.

    Returns:
        rdflib.Graph with OWL ontology triples.
    """
    logger.debug("[Ontology] Building graph | namespace=%s | classes=%d | object_props=%d | datatype_props=%d",
                 schema.namespace_uri, len(schema.classes), len(schema.object_properties), len(schema.datatype_properties))
    g = Graph()
    base = schema.namespace_uri.rstrip("#") + "#"
    ns = Namespace(base)
    g.bind(schema.namespace_prefix, ns)
    g.bind("xsd", XSD)

    ont_uri = URIRef(base)
    g.add((ont_uri, RDF.type, OWL.Ontology))
    g.add((ont_uri, RDFS.label, Literal(f"Ontology from {schema.namespace_prefix}")))
    logger.debug("[Ontology] Ontology header added")

    # Classes
    for c in schema.classes:
        uri = ns[c.name]
        g.add((uri, RDF.type, OWL.Class))
        if c.parent:
            parent_uri = ns[c.parent]
            g.add((uri, RDFS.subClassOf, parent_uri))

    # Object properties
    for p in schema.object_properties:
        uri = ns[p.name]
        g.add((uri, RDF.type, OWL.ObjectProperty))
        g.add((uri, RDFS.domain, ns[p.domain]))
        g.add((uri, RDFS.range, ns[p.range]))

    # Datatype properties
    for p in schema.datatype_properties:
        uri = ns[p.name]
        g.add((uri, RDF.type, OWL.DatatypeProperty))
        g.add((uri, RDFS.domain, ns[p.domain]))
        range_uri = XSD_BY_NAME.get(p.range.lower(), XSD.string)
        g.add((uri, RDFS.range, range_uri))

    logger.debug("[Ontology] Graph built | triples=%d", len(g))
    return g


def serialize_ontology(graph: Graph, format: str) -> str | bytes:
    """Serialize the rdflib graph to a string or bytes.

    Args:
        graph: rdflib Graph to serialize.
        format: One of 'owl', 'xml', 'turtle', 'json-ld'.

    Returns:
        Serialized ontology as str or bytes.

    Raises:
        ValueError: If format is unsupported.
    """
    logger.debug("[Ontology] Serializing | format=%s | triples=%d", format, len(graph))
    if format == "xml" or format == "owl":
        return graph.serialize(format="xml")
    if format == "turtle":
        return graph.serialize(format="turtle")
    if format == "json-ld":
        return graph.serialize(format="json-ld")
    raise ValueError(f"Unsupported format: {format}. Use owl, turtle, or json-ld.")
