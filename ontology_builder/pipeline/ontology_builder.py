"""Merge extracted entities and relations into graph. Canonicalizes entity names before adding."""

import logging
import sys

from tqdm import tqdm

from ontology_builder.ontology.canonicalizer import canonicalize
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def update_graph(graph: OntologyGraph, extraction: dict, verbose: bool = True) -> None:
    """Merge extracted entities and relations into the graph.

    Canonicalizes entity names via embedding similarity before adding.
    Skips entities/relations with missing names.

    Args:
        graph: OntologyGraph to update.
        extraction: Dict with "entities" and "relations" lists.
        verbose: If True, show tqdm progress for entities and relations.
    """
    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])
    logger.debug("[OntologyBuilder] Updating graph | entities=%d | relations=%d", len(entities), len(relations))

    for e in tqdm(entities, desc="Adding entities", disable=not verbose, unit="entity", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        name = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "Entity")
        if name:
            canonical = canonicalize(name)
            graph.add_entity(canonical, etype)
            if canonical != name:
                logger.debug("[OntologyBuilder] Canonicalized entity: %r -> %r", name, canonical)

    for r in tqdm(relations, desc="Adding relations", disable=not verbose, unit="relation", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        if isinstance(r, dict):
            source = r.get("source")
            relation = r.get("relation", "related_to")
            target = r.get("target")
        else:
            source = getattr(r, "source", None)
            relation = getattr(r, "relation", "related_to")
            target = getattr(r, "target", None)
        if source and target:
            src_canonical = canonicalize(source)
            tgt_canonical = canonicalize(target)
            graph.add_relation(src_canonical, relation, tgt_canonical)
