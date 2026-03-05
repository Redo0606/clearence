"""Export OntologyGraph to OWL/RDF in reusable standard formats.

Supports Turtle (TTL), JSON-LD, and RDF/XML — the most widely adopted formats
for ontology exchange per W3C standards. Turtle is human-readable and compact;
JSON-LD integrates well with JSON-based systems; RDF/XML is the classic format.
"""

from __future__ import annotations

import re
import urllib.parse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from ontology_builder.storage.graphdb import OntologyGraph

# XSD datatype mapping for data properties
XSD_BY_NAME: dict[str, URIRef] = {
    "string": XSD.string,
    "str": XSD.string,
    "int": XSD.integer,
    "integer": XSD.integer,
    "float": XSD.double,
    "double": XSD.double,
    "number": XSD.decimal,
    "date": XSD.date,
    "datetime": XSD.dateTime,
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
}


def _to_uri_safe(s: str) -> str:
    """Convert a label to a URI-safe local name (no spaces, valid chars)."""
    if not s:
        return "entity"
    # Replace problematic chars; keep alphanumeric, underscore, hyphen
    safe = re.sub(r"[^\w\-]", "_", s.strip())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "entity"


def _uri(base: str, local: str) -> URIRef:
    """Build a URIRef from base namespace and local name."""
    safe = _to_uri_safe(local)
    return URIRef(base.rstrip("#") + "#" + urllib.parse.quote(safe, safe=""))


def ontology_graph_to_rdflib(
    graph: OntologyGraph,
    base_uri: str = "http://example.org/ontology#",
    ontology_label: str | None = None,
) -> Graph:
    """Convert OntologyGraph to an rdflib Graph (OWL/RDF).

    Maps:
    - Classes -> owl:Class with rdfs:subClassOf
    - Instances -> owl:NamedIndividual with rdf:type
    - Object relations -> owl:ObjectProperty assertions
    - Data properties -> owl:DatatypeProperty assertions
    - Axioms -> OWL axioms (disjointness, etc.)

    Args:
        graph: OntologyGraph from the knowledge base.
        base_uri: Base URI for the ontology (default: http://example.org/ontology#).
        ontology_label: Optional label for the ontology.

    Returns:
        rdflib.Graph with OWL/RDF triples.
    """
    if not isinstance(graph, OntologyGraph):
        raise TypeError("graph must be an OntologyGraph")

    g = Graph()
    base = base_uri.rstrip("#") + "#"
    ns = Namespace(base)
    g.bind("", ns)
    g.bind("owl", OWL)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    ont_uri = URIRef(base)
    g.add((ont_uri, RDF.type, OWL.Ontology))
    label = ontology_label or "Exported ontology"
    g.add((ont_uri, RDFS.label, Literal(label)))

    nx_graph = graph.get_graph()
    classes = set(graph.get_classes())
    instances = set(graph.get_instances())

    # Declare all classes
    for name in classes:
        uri = _uri(base, name)
        g.add((uri, RDF.type, OWL.Class))
        desc = graph.get_node_description(name)
        if desc:
            g.add((uri, RDFS.comment, Literal(desc)))
        for syn in graph.get_node_synonyms(name):
            g.add((uri, ns.altLabel, Literal(syn)))

    # Declare all instances and their types
    for name in instances:
        uri = _uri(base, name)
        g.add((uri, RDF.type, OWL.NamedIndividual))
        node_data = nx_graph.nodes.get(name, {})
        etype = node_data.get("type", "Thing")
        type_uri = _uri(base, etype)
        g.add((uri, RDF.type, type_uri))
        desc = graph.get_node_description(name)
        if desc:
            g.add((uri, RDFS.comment, Literal(desc)))

    # subClassOf edges
    for src, tgt, data in nx_graph.edges(data=True):
        if data.get("relation") != "subClassOf":
            continue
        if src in classes and tgt in classes:
            g.add((_uri(base, src), RDFS.subClassOf, _uri(base, tgt)))

    # type edges (instance -> class)
    for src, tgt, data in nx_graph.edges(data=True):
        if data.get("relation") != "type":
            continue
        if src in instances and tgt in classes:
            g.add((_uri(base, src), RDF.type, _uri(base, tgt)))

    # Object property edges (relations between entities)
    # Collect unique relation names and declare them as ObjectProperties
    relation_names: set[str] = set()
    for src, tgt, data in nx_graph.edges(data=True):
        rel = data.get("relation", "related_to")
        if rel in ("subClassOf", "type"):
            continue
        relation_names.add(rel)

    for rel_name in relation_names:
        prop_uri = _uri(base, rel_name)
        g.add((prop_uri, RDF.type, OWL.ObjectProperty))

    for src, tgt, data in nx_graph.edges(data=True):
        rel = data.get("relation", "related_to")
        if rel in ("subClassOf", "type"):
            continue
        src_uri = _uri(base, src)
        tgt_uri = _uri(base, tgt)
        prop_uri = _uri(base, rel)
        g.add((src_uri, prop_uri, tgt_uri))

    # Data properties
    for dp in graph.data_properties:
        entity = dp.get("entity", "")
        attr = dp.get("attribute", "")
        val = dp.get("value", "")
        dtype = dp.get("datatype", "string")
        if not entity or not attr:
            continue
        entity_uri = _uri(base, entity)
        prop_uri = _uri(base, attr)
        g.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        xsd_type = XSD_BY_NAME.get(dtype.lower(), XSD.string)
        g.add((entity_uri, prop_uri, Literal(val, datatype=xsd_type)))

    # Axioms
    for axiom in graph.axioms:
        atype = axiom.get("axiom_type", "")
        entities = axiom.get("entities", [])
        if atype == "disjointness" and len(entities) >= 2:
            c1, c2 = _uri(base, entities[0]), _uri(base, entities[1])
            g.add((c1, OWL.disjointWith, c2))
        elif atype == "transitivity" and len(entities) >= 1:
            prop_uri = _uri(base, entities[0])
            g.add((prop_uri, RDF.type, OWL.TransitiveProperty))
        elif atype == "symmetry" and len(entities) >= 1:
            prop_uri = _uri(base, entities[0])
            g.add((prop_uri, RDF.type, OWL.SymmetricProperty))
        elif atype == "inverse" and len(entities) >= 2:
            p1, p2 = _uri(base, entities[0]), _uri(base, entities[1])
            g.add((p1, OWL.inverseOf, p2))

    return g


def export_ontology_to_rdf(
    graph: OntologyGraph,
    format: str = "turtle",
    base_uri: str = "http://example.org/ontology#",
    ontology_label: str | None = None,
) -> str | bytes:
    """Export OntologyGraph to a serialized RDF string.

    Args:
        graph: OntologyGraph to export.
        format: One of 'turtle', 'ttl', 'json-ld', 'jsonld', 'xml', 'rdf+xml', 'owl'.
        base_uri: Base URI for the ontology.
        ontology_label: Optional label for the ontology.

    Returns:
        Serialized ontology as str (turtle, json-ld) or bytes (xml).

    Raises:
        ValueError: If format is unsupported.
    """
    rdf_graph = ontology_graph_to_rdflib(graph, base_uri, ontology_label)
    fmt = format.lower().strip()
    if fmt in ("turtle", "ttl"):
        return rdf_graph.serialize(format="turtle")
    if fmt in ("json-ld", "jsonld"):
        return rdf_graph.serialize(format="json-ld")
    if fmt in ("xml", "rdf+xml", "owl", "rdf"):
        return rdf_graph.serialize(format="xml")
    if fmt == "nt" or fmt == "n-triples":
        return rdf_graph.serialize(format="nt")
    raise ValueError(
        f"Unsupported format: {format}. Use: turtle, json-ld, xml, nt"
    )
