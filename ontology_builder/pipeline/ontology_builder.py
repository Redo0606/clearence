"""Merge extracted entities and relations into graph. Canonicalizes entity names before adding.

Supports both legacy dict format and the new structured OntologyExtraction,
and aggregated format (vote_count, chunk_ids, confidence) for batched pipeline updates.
"""

import logging
import sys
from pathlib import Path
from typing import Any

from tqdm import tqdm

from core.config import get_settings
from ontology_builder.ontology.canonicalizer import canonicalize, canonicalize_batch
from ontology_builder.ontology.schema import OntologyExtraction
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def _norm_source_doc(path_or_name: str) -> str:
    """Normalize path or document name to basename for provenance storage."""
    s = (path_or_name or "").strip()
    if not s:
        return ""
    return Path(s).name or s


def update_graph(
    graph: OntologyGraph,
    extraction: dict | OntologyExtraction,
    verbose: bool = True,
    chunk_id: int | None = None,
) -> None:
    """Merge extracted entities and relations into the graph.

    Canonicalizes entity names via embedding similarity before adding.
    chunk_id: optional chunk index for provenance (Plan 2 relation correctness).
    """
    if isinstance(extraction, OntologyExtraction):
        _update_graph_structured(graph, extraction, verbose, chunk_id=chunk_id)
        return

    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])
    logger.debug("[OntologyBuilder] Updating graph | entities=%d | relations=%d", len(entities), len(relations))

    for e in tqdm(entities, desc="Adding entities", disable=not verbose, unit="entity", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        name = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "Entity")
        if name:
            kind = "class" if etype in ("Class", "Concept", "Category") else "instance"
            canonical = canonicalize(name, kind=kind)
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
            src_canonical = canonicalize(source, kind="entity")
            tgt_canonical = canonicalize(target, kind="entity")
            extra = {k: v for k, v in (r if isinstance(r, dict) else {}).items() if k not in ("source", "relation", "target", "confidence")}
            graph.add_relation(src_canonical, relation, tgt_canonical, confidence=confidence, **extra)


def _get_extraction_source_doc(extraction: OntologyExtraction) -> str:
    """Get normalized source document from first available element."""
    for cls in extraction.classes:
        if cls.source_document:
            return _norm_source_doc(cls.source_document)
    for inst in extraction.instances:
        if inst.source_document:
            return _norm_source_doc(inst.source_document)
    for op in extraction.object_properties:
        if op.source_document:
            return _norm_source_doc(op.source_document)
    for dp in extraction.data_properties:
        if dp.source_document:
            return _norm_source_doc(dp.source_document)
    return ""


def _update_graph_structured(
    graph: OntologyGraph,
    extraction: OntologyExtraction,
    verbose: bool,
    chunk_id: int | None = None,
) -> None:
    """Merge a structured OntologyExtraction with canonicalization and provenance."""
    fallback_doc = _get_extraction_source_doc(extraction)
    prov: dict = {"origin": "extraction"}
    if chunk_id is not None:
        prov["chunk_id"] = chunk_id
    for cls in tqdm(extraction.classes, desc="Adding classes", disable=not verbose, unit="cls", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        canonical = canonicalize(cls.name, kind="class")
        parent = canonicalize(cls.parent, kind="class") if cls.parent else None
        doc = _norm_source_doc(cls.source_document) or fallback_doc
        graph.add_class(canonical, cls.description, parent, synonyms=cls.synonyms or None, source_document=doc or None)

    for inst in tqdm(extraction.instances, desc="Adding instances", disable=not verbose, unit="inst", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        canonical = canonicalize(inst.name, kind="instance")
        class_canonical = canonicalize(inst.class_name, kind="class")
        doc = _norm_source_doc(inst.source_document) or fallback_doc
        graph.add_instance(canonical, class_canonical, inst.description, source_document=doc or None)

    for op in tqdm(extraction.object_properties, desc="Adding relations", disable=not verbose, unit="rel", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        src = canonicalize(op.source, kind="entity")
        tgt = canonicalize(op.target, kind="entity")
        doc = _norm_source_doc(op.source_document) or fallback_doc
        graph.add_relation(
            src, op.relation, tgt,
            confidence=op.confidence,
            source_document=doc or None,
            provenance=prov,
        )

    for dp in extraction.data_properties:
        entity = canonicalize(dp.entity, kind="entity")
        doc = _norm_source_doc(dp.source_document) or fallback_doc
        graph.add_data_property(entity, dp.attribute, dp.value, dp.datatype, source_document=doc or None)

    for ax in extraction.axioms:
        graph.add_axiom(ax.model_dump())

    logger.info(
        "[OntologyBuilder] Structured merge | classes=%d instances=%d relations=%d axioms=%d",
        len(extraction.classes),
        len(extraction.instances),
        len(extraction.object_properties),
        len(extraction.axioms),
    )


def update_graph_from_aggregated(
    graph: OntologyGraph,
    aggregated: dict[str, Any],
    source_document: str | None = None,
    verbose: bool = False,
) -> None:
    """Update graph from pre-aggregated data (relations with vote_count, chunk_ids; classes/instances with chunk_ids).

    Uses add_relations_batch and batch-sized loops for speed. Names in aggregated are already canonical.
    """
    batch_size = max(1, get_settings().graph_write_batch_size)
    relations = aggregated.get("relations", [])
    classes = aggregated.get("classes", [])
    instances = aggregated.get("instances", [])
    data_properties = aggregated.get("data_properties", [])
    axioms = aggregated.get("axioms", [])

    for start in range(0, len(classes), batch_size):
        batch = classes[start : start + batch_size]
        for c in batch:
            graph.add_class(
                c["name"],
                c.get("description", ""),
                c.get("parent"),
                synonyms=c.get("synonyms") or None,
                chunk_ids=c.get("chunk_ids"),
                vote_count=c.get("vote_count"),
                source_document=source_document,
            )

    for start in range(0, len(instances), batch_size):
        batch = instances[start : start + batch_size]
        for i in batch:
            class_name = i.get("class_name", "")
            graph.add_instance(
                i["name"],
                class_name,
                i.get("description", ""),
                source_document=source_document,
                chunk_ids=i.get("chunk_ids"),
                vote_count=i.get("vote_count"),
            )

    graph.add_relations_batch(relations, batch_size=batch_size)

    for dp in data_properties:
        entity = canonicalize(dp.get("entity", ""), kind="entity")
        graph.add_data_property(
            entity,
            dp.get("attribute", ""),
            dp.get("value", ""),
            dp.get("datatype", "string"),
            source_document=source_document,
        )

    for ax in axioms:
        graph.add_axiom(ax if isinstance(ax, dict) else (ax.model_dump() if hasattr(ax, "model_dump") else {}))

    logger.info(
        "[OntologyBuilder] Aggregated merge | classes=%d instances=%d relations=%d axioms=%d",
        len(classes),
        len(instances),
        len(relations),
        len(axioms),
    )
