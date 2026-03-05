"""Merge extracted entities and relations into graph. Canonicalizes entity names before adding.

Supports both legacy dict format and the new structured OntologyExtraction.
"""

import logging
import sys

from tqdm import tqdm

from ontology_builder.ontology.canonicalizer import canonicalize
from ontology_builder.ontology.schema import OntologyExtraction
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def update_graph(graph: OntologyGraph, extraction: dict | OntologyExtraction, verbose: bool = True) -> None:
    """Merge extracted entities and relations into the graph.

    Canonicalizes entity names via embedding similarity before adding.
    Accepts both legacy dicts and structured OntologyExtraction.
    """
    if isinstance(extraction, OntologyExtraction):
        _update_graph_structured(graph, extraction, verbose)
        return

    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])
    logger.debug("[OntologyBuilder] Updating graph | entities=%d | relations=%d", len(entities), len(relations))

    for e in tqdm(entities, desc="Adding entities", disable=not verbose, unit="entity", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        name = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "Entity")
        if name:
            canonical = canonicalize(name)
            kind = "class" if etype in ("Class", "Concept", "Category") else "instance"
            graph.add_entity(canonical, etype, kind=kind)
            if canonical != name:
                logger.debug("[OntologyBuilder] Canonicalized entity: %r -> %r", name, canonical)

    for r in tqdm(relations, desc="Adding relations", disable=not verbose, unit="relation", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        if isinstance(r, dict):
            source = r.get("source")
            relation = r.get("relation", "related_to")
            target = r.get("target")
            confidence = float(r.get("confidence", 1.0))
        else:
            source = getattr(r, "source", None)
            relation = getattr(r, "relation", "related_to")
            target = getattr(r, "target", None)
            confidence = float(getattr(r, "confidence", 1.0))
        if source and target:
            src_canonical = canonicalize(source)
            tgt_canonical = canonicalize(target)
            graph.add_relation(src_canonical, relation, tgt_canonical, confidence=confidence)


def _update_graph_structured(graph: OntologyGraph, extraction: OntologyExtraction, verbose: bool) -> None:
    """Merge a structured OntologyExtraction with canonicalization."""
    for cls in tqdm(extraction.classes, desc="Adding classes", disable=not verbose, unit="cls", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        canonical = canonicalize(cls.name)
        parent = canonicalize(cls.parent) if cls.parent else None
        graph.add_class(canonical, cls.description, parent)

    for inst in tqdm(extraction.instances, desc="Adding instances", disable=not verbose, unit="inst", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        canonical = canonicalize(inst.name)
        class_canonical = canonicalize(inst.class_name)
        graph.add_instance(canonical, class_canonical, inst.description)

    for op in tqdm(extraction.object_properties, desc="Adding relations", disable=not verbose, unit="rel", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        src = canonicalize(op.source)
        tgt = canonicalize(op.target)
        graph.add_relation(src, op.relation, tgt, confidence=op.confidence)

    for dp in extraction.data_properties:
        entity = canonicalize(dp.entity)
        graph.add_data_property(entity, dp.attribute, dp.value, dp.datatype)

    for ax in extraction.axioms:
        graph.add_axiom(ax.model_dump())

    logger.info(
        "[OntologyBuilder] Structured merge | classes=%d instances=%d relations=%d axioms=%d",
        len(extraction.classes),
        len(extraction.instances),
        len(extraction.object_properties),
        len(extraction.axioms),
    )
