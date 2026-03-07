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
from ontology_builder.ontology.schema import normalize_relation_name
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

    # Batched for 10-50x speedup over per-entity encoding
    entity_names = []
    entity_kinds = []
    for e in entities:
        name = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "Entity")
        if name:
            kind = "class" if etype in ("Class", "Concept", "Category") else "instance"
            entity_names.append(name)
            entity_kinds.append(kind)
    entity_canonical = {}
    if entity_names:
        for kind in ("class", "instance"):
            indices = [i for i, k in enumerate(entity_kinds) if k == kind]
            if indices:
                names = [entity_names[i] for i in indices]
                canon = canonicalize_batch(names, kind=kind)
                for i, c in zip(indices, canon):
                    entity_canonical[(entity_names[i], kind)] = c

    for e in tqdm(entities, desc="Adding entities", disable=not verbose, unit="entity", file=sys.stderr, dynamic_ncols=True, mininterval=0.5):
        name = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "Entity")
        if name:
            kind = "class" if etype in ("Class", "Concept", "Category") else "instance"
            canonical = entity_canonical.get((name, kind), canonicalize(name, kind=kind))
            graph.add_entity(canonical, etype, kind=kind)
            if canonical != name:
                logger.debug("[OntologyBuilder] Canonicalized entity: %r -> %r", name, canonical)

    # Batched for 10-50x speedup over per-entity encoding
    rel_sources = []
    rel_targets = []
    for r in relations:
        if isinstance(r, dict):
            source, target = r.get("source"), r.get("target")
        else:
            source, target = getattr(r, "source", None), getattr(r, "target", None)
        if source and target:
            rel_sources.append(source)
            rel_targets.append(target)
    rel_canonical = {}
    if rel_sources:
        src_canon = canonicalize_batch(rel_sources, kind="entity")
        tgt_canon = canonicalize_batch(rel_targets, kind="entity")
        for i, (s, t) in enumerate(zip(rel_sources, rel_targets)):
            rel_canonical[(s, t)] = (src_canon[i], tgt_canon[i])

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
            src_canonical, tgt_canonical = rel_canonical.get((source, target), (canonicalize(source, kind="entity"), canonicalize(target, kind="entity")))
            rel = normalize_relation_name(relation)
            extra = {k: v for k, v in (r if isinstance(r, dict) else {}).items() if k not in ("source", "relation", "target", "confidence")}
            graph.add_relation(src_canonical, rel, tgt_canonical, confidence=confidence, **extra)


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

    # Batched for 10-50x speedup over per-entity encoding
    class_names = [cls.name for cls in extraction.classes]
    unique_parents = list(dict.fromkeys(cls.parent for cls in extraction.classes if cls.parent))
    cls_canonical = canonicalize_batch(class_names, kind="class") if class_names else []
    parent_canonical = canonicalize_batch(unique_parents, kind="class") if unique_parents else []
    parent_lookup = dict(zip(unique_parents, parent_canonical)) if unique_parents else {}

    inst_names = [inst.name for inst in extraction.instances]
    inst_classes = [inst.class_name for inst in extraction.instances]
    inst_canonical = canonicalize_batch(inst_names, kind="instance") if inst_names else []
    inst_class_canonical = canonicalize_batch(inst_classes, kind="class") if inst_classes else []

    op_sources = [op.source for op in extraction.object_properties]
    op_targets = [op.target for op in extraction.object_properties]
    op_src_canonical = canonicalize_batch(op_sources, kind="entity") if op_sources else []
    op_tgt_canonical = canonicalize_batch(op_targets, kind="entity") if op_targets else []

    for i, cls in enumerate(tqdm(extraction.classes, desc="Adding classes", disable=not verbose, unit="cls", file=sys.stderr, dynamic_ncols=True, mininterval=0.5)):
        canonical = cls_canonical[i] if i < len(cls_canonical) else canonicalize(cls.name, kind="class")
        parent = parent_lookup.get(cls.parent) if cls.parent else None
        doc = _norm_source_doc(cls.source_document) or fallback_doc
        graph.add_class(
            canonical,
            cls.description,
            parent,
            synonyms=cls.synonyms or None,
            source_document=doc or None,
            salience=getattr(cls, "salience", None),
            domain_tags=getattr(cls, "domain_tags", None) or None,
        )

    dp_count = 0
    for i, inst in enumerate(tqdm(extraction.instances, desc="Adding instances", disable=not verbose, unit="inst", file=sys.stderr, dynamic_ncols=True, mininterval=0.5)):
        canonical = inst_canonical[i] if i < len(inst_canonical) else canonicalize(inst.name, kind="instance")
        class_canonical = inst_class_canonical[i] if i < len(inst_class_canonical) else canonicalize(inst.class_name, kind="class")
        doc = _norm_source_doc(inst.source_document) or fallback_doc
        attrs = getattr(inst, "attributes", None) or {}
        graph.add_instance(
            canonical,
            class_canonical,
            inst.description,
            source_document=doc or None,
            attributes=attrs if attrs else None,
        )
        dp_count += len(attrs) if attrs else 0

    for i, op in enumerate(tqdm(extraction.object_properties, desc="Adding relations", disable=not verbose, unit="rel", file=sys.stderr, dynamic_ncols=True, mininterval=0.5)):
        src = op_src_canonical[i] if i < len(op_src_canonical) else canonicalize(op.source, kind="entity")
        tgt = op_tgt_canonical[i] if i < len(op_tgt_canonical) else canonicalize(op.target, kind="entity")
        doc = _norm_source_doc(op.source_document) or fallback_doc
        rel = normalize_relation_name(op.relation)
        edge_attrs: dict = {}
        if getattr(op, "evidence", ""):
            edge_attrs["evidence"] = op.evidence
        if getattr(op, "relation_type", ""):
            edge_attrs["relation_type"] = op.relation_type
        graph.add_relation(
            src,
            rel,
            tgt,
            confidence=op.confidence,
            source_document=doc or None,
            provenance=prov,
            **edge_attrs,
        )

    for dp in extraction.data_properties:
        entity = canonicalize(dp.entity, kind="entity")
        doc = _norm_source_doc(dp.source_document) or fallback_doc
        graph.add_data_property(entity, dp.attribute, dp.value, dp.datatype, source_document=doc or None)

    for ax in extraction.axioms:
        graph.add_axiom(ax.model_dump())

    if dp_count:
        logger.info("Created %d data properties from inline instance attributes", dp_count)
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

    normalized_relations = []
    for r in relations:
        r = dict(r)
        if r.get("relation"):
            r["relation"] = normalize_relation_name(r["relation"])
        normalized_relations.append(r)
    graph.add_relations_batch(normalized_relations, batch_size=batch_size)

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
