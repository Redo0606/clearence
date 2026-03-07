"""NetworkX-based ontology graph with class/instance distinctions, axiom storage,
and structured fact representation (OG-RAG-ready).

Extends the basic DiGraph wrapper with:
  - Node kind: "class" vs "instance" (for downstream reasoning/visualization)
  - Axiom store: disjointness, symmetry, transitivity, etc.
  - Structured facts: each edge carries key/value/full for OG-RAG hypergraph construction
  - Factual block export for hypergraph building
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from core.config import get_settings
from ontology_builder.embeddings import get_embedding_model
from ontology_builder.ontology.schema import (
    Axiom,
    OntologyClass,
    OntologyExtraction,
    OntologyInstance,
)

logger = logging.getLogger(__name__)


def _merge_source_documents(existing: list[str] | None, new: str | None) -> list[str]:
    """Merge source document into list, deduplicated."""
    if not new:
        return list(existing) if existing else []
    result = list(existing) if existing else []
    # Normalize: use basename for consistency
    doc = new.strip()
    if doc and doc not in result:
        result.append(doc)
    return result


def _merge_chunk_ids(existing: list[int] | None, new: list[int] | None) -> list[int]:
    """Merge chunk_id lists, deduplicated, sorted."""
    seen: set[int] = set(existing or [])
    for cid in new or []:
        seen.add(int(cid))
    return sorted(seen)


class OntologyGraph:
    """NetworkX DiGraph wrapper for formal ontology with class/instance nodes and axioms."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._axioms: list[dict[str, Any]] = []
        self._data_properties: list[dict[str, Any]] = []
        self.embedding_cache: dict[str, Any] = {}  # node name -> np.ndarray (filled at add time)
        self._loading_mode = False

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_entity(
        self,
        name: str,
        etype: str,
        kind: str = "class",
        chunk_ids: list[int] | None = None,
        vote_count: int | None = None,
        **attrs: Any,
    ) -> None:
        """Add an entity node. If node exists, merges chunk_ids and keeps longer description.

        Args:
            name: Entity identifier.
            etype: Semantic type label (e.g. "Concept", "Person").
            kind: "class" or "instance".
            chunk_ids: Chunk indices that contributed this node (for vote/confidence).
            vote_count: Optional pre-aggregated vote count (used when chunk_ids not provided).
            **attrs: Extra attributes (description, source_documents, confidence, etc.).
        """
        attrs = dict(attrs)
        if name in self.graph:
            existing = dict(self.graph.nodes[name])
            merged_chunk_ids = _merge_chunk_ids(
                existing.get("chunk_ids"),
                chunk_ids or ([] if vote_count is None else list(range(vote_count))),
            )
            merged_desc = max(
                (attrs.get("description") or "").strip(),
                (existing.get("description") or "").strip(),
                key=len,
            )
            attrs["chunk_ids"] = merged_chunk_ids
            attrs["vote_count"] = vote_count if vote_count is not None else len(merged_chunk_ids)
            if merged_desc:
                attrs["description"] = merged_desc
            existing.update(attrs)
            attrs = existing
        else:
            vc = vote_count if vote_count is not None else (len(chunk_ids) if chunk_ids else 1)
            if chunk_ids is not None:
                attrs["chunk_ids"] = list(chunk_ids)
            attrs["vote_count"] = vc
        # Avoid duplicate keyword: attrs may contain type/kind when merging existing node
        node_attrs = {k: v for k, v in attrs.items() if k not in ("type", "kind")}
        self.graph.add_node(name, type=etype, kind=kind, **node_attrs)
        if not self._loading_mode:
            desc = attrs.get("description", "") or self.graph.nodes[name].get("description", "") or ""
            text = f"{name} {desc}".strip() or name
            try:
                model = get_embedding_model()
                self.embedding_cache[name] = model.encode(
                    text, convert_to_numpy=True, show_progress_bar=False
                )
            except Exception as e:
                logger.debug("[GraphDB] Embedding cache skip for %r: %s", name, e)

    def add_class(
        self,
        name: str,
        description: str = "",
        parent: str | None = None,
        synonyms: list[str] | None = None,
        source_document: str | None = None,
        chunk_ids: list[int] | None = None,
        vote_count: int | None = None,
        salience: float | None = None,
        domain_tags: list[str] | None = None,
    ) -> None:
        attrs: dict[str, Any] = {}
        if synonyms:
            attrs["synonyms"] = list(synonyms)
        if salience is not None:
            attrs["salience"] = float(salience)
        if domain_tags:
            attrs["domain_tags"] = list(domain_tags)
        if source_document:
            attrs["source_documents"] = _merge_source_documents(
                self.graph.nodes.get(name, {}).get("source_documents", []),
                source_document,
            )
        self.add_entity(name, etype="Class", kind="class", description=description, chunk_ids=chunk_ids, vote_count=vote_count, **attrs)
        if parent:
            self.add_relation(name, "subClassOf", parent, source_document=source_document)

    def add_instance(
        self,
        name: str,
        class_name: str,
        description: str = "",
        source_document: str | None = None,
        provenance: dict | None = None,
        chunk_ids: list[int] | None = None,
        vote_count: int | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        attrs: dict[str, Any] = {}
        if source_document:
            attrs["source_documents"] = _merge_source_documents(
                self.graph.nodes.get(name, {}).get("source_documents", []),
                source_document,
            )
        self.add_entity(name, etype=class_name, kind="instance", description=description, chunk_ids=chunk_ids, vote_count=vote_count, **attrs)
        if class_name and class_name in self.graph:
            self.add_relation(
                name, "type", class_name,
                source_document=source_document,
                provenance=provenance,
            )
        if attributes:
            for attr_name, attr_val in attributes.items():
                if attr_name and attr_val is not None:
                    self.add_data_property(name, attr_name, str(attr_val), "string", source_document=source_document)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_relation(
        self,
        source: str,
        relation: str,
        target: str,
        confidence: float = 1.0,
        source_document: str | None = None,
        provenance: dict | None = None,
        vote_count: int | None = None,
        chunk_ids: list[int] | None = None,
        **attrs: Any,
    ) -> None:
        """Add a directed relation edge. When same (source, target, relation) exists, merges votes and confidence."""
        key_field = f"{source}: {relation}"
        full_field = f"{source}: {relation} -> {target}"
        edge_attrs = {k: v for k, v in attrs.items() if k not in ("key", "value", "full")}
        if provenance is not None:
            edge_attrs["provenance"] = dict(provenance)
        if vote_count is not None:
            edge_attrs["vote_count"] = vote_count
        if chunk_ids is not None:
            edge_attrs["chunk_ids"] = list(chunk_ids)
        if source_document:
            if self.graph.has_edge(source, target):
                existing = self.graph[source][target]
                edge_attrs["source_documents"] = _merge_source_documents(
                    existing.get("source_documents", []),
                    source_document,
                )
            else:
                edge_attrs["source_documents"] = _merge_source_documents([], source_document)

        if self.graph.has_edge(source, target) and self.graph[source][target].get("relation") == relation:
            # Merge: same triple from another chunk
            existing = self.graph[source][target]
            existing_votes = existing.get("vote_count", 1)
            existing_chunks = existing.get("chunk_ids") or []
            existing_conf = float(existing.get("confidence", 1.0))
            new_votes = vote_count if vote_count is not None else (len(chunk_ids) if chunk_ids else 1)
            new_chunks = chunk_ids or []
            merged_chunks = _merge_chunk_ids(existing_chunks, new_chunks)
            total_votes = len(merged_chunks) if merged_chunks else (existing_votes + new_votes)
            # Running average confidence
            n_old = existing_votes if existing_votes else 1
            n_new = new_votes if new_votes else 1
            merged_conf = (existing_conf * n_old + confidence * n_new) / (n_old + n_new)
            edge_attrs["vote_count"] = total_votes
            edge_attrs["chunk_ids"] = merged_chunks
            edge_attrs["confidence"] = min(1.0, merged_conf)
        else:
            edge_attrs["confidence"] = confidence

        self.graph.add_edge(
            source,
            target,
            relation=relation,
            key=key_field,
            value=target,
            full=full_field,
            **edge_attrs,
        )

    def add_relations_batch(
        self,
        relations: list[dict[str, Any]],
        batch_size: int | None = None,
    ) -> None:
        """Add multiple relations in batches. Each dict has source, relation, target, confidence, and optional vote_count, chunk_ids, provenance, source_document."""
        if not relations:
            return
        batch_size = batch_size or max(1, get_settings().graph_write_batch_size)
        for start in range(0, len(relations), batch_size):
            batch = relations[start : start + batch_size]
            for r in batch:
                src = r.get("source")
                rel = r.get("relation", "related_to")
                tgt = r.get("target")
                if not src or not tgt:
                    continue
                conf = float(r.get("confidence", 1.0))
                self.add_relation(
                    src,
                    rel,
                    tgt,
                    confidence=conf,
                    source_document=r.get("source_document"),
                    provenance=r.get("provenance"),
                    vote_count=r.get("vote_count"),
                    chunk_ids=r.get("chunk_ids"),
                )

    # ------------------------------------------------------------------
    # Axiom operations
    # ------------------------------------------------------------------

    def add_axiom(self, axiom: dict[str, Any]) -> None:
        self._axioms.append(axiom)

    @property
    def axioms(self) -> list[dict[str, Any]]:
        return list(self._axioms)

    # ------------------------------------------------------------------
    # Data property operations
    # ------------------------------------------------------------------

    def add_data_property(
        self,
        entity: str,
        attribute: str,
        value: str,
        datatype: str = "string",
        source_document: str | None = None,
        source_documents: list[str] | None = None,
    ) -> None:
        dp: dict[str, Any] = {
            "entity": entity,
            "attribute": attribute,
            "value": value,
            "datatype": datatype,
        }
        if source_documents:
            dp["source_documents"] = list(source_documents)
        elif source_document:
            dp["source_documents"] = [source_document]
        self._data_properties.append(dp)
        self.graph.add_node(entity, **{attribute: value})

    @property
    def data_properties(self) -> list[dict[str, Any]]:
        return list(self._data_properties)

    # ------------------------------------------------------------------
    # Merge from structured extraction
    # ------------------------------------------------------------------

    def merge_extraction(self, extraction: OntologyExtraction) -> None:
        """Merge a structured OntologyExtraction into this graph."""
        for cls in extraction.classes:
            self.add_class(cls.name, cls.description, cls.parent)
        for inst in extraction.instances:
            self.add_instance(inst.name, inst.class_name, inst.description)
        for op in extraction.object_properties:
            self.add_relation(op.source, op.relation, op.target, op.confidence)
        for dp in extraction.data_properties:
            self.add_data_property(dp.entity, dp.attribute, dp.value, dp.datatype)
        for ax in extraction.axioms:
            self.add_axiom(ax.model_dump())

    # ------------------------------------------------------------------
    # OG-RAG factual blocks
    # ------------------------------------------------------------------

    def to_factual_blocks(self) -> list[dict[str, Any]]:
        """Convert graph to OG-RAG factual blocks F.

        Each factual block is a dict with subject, attributes (list of
        {relation, target, key, value, full}).
        """
        blocks: list[dict[str, Any]] = []
        for node in self.graph.nodes:
            attrs = []
            for _, target, data in self.graph.out_edges(node, data=True):
                attrs.append({
                    "relation": data.get("relation", "related_to"),
                    "target": target,
                    "key": data.get("key", ""),
                    "value": data.get("value", ""),
                    "full": data.get("full", ""),
                })
            if attrs:
                blocks.append({"subject": node, "attributes": attrs})

        for dp in self._data_properties:
            blocks.append({
                "subject": dp["entity"],
                "attributes": [{
                    "relation": dp["attribute"],
                    "target": dp["value"],
                    "key": f"{dp['entity']}: {dp['attribute']}",
                    "value": dp["value"],
                    "full": f"{dp['entity']}: {dp['attribute']} = {dp['value']}",
                }],
            })
        return blocks

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_classes(self) -> list[str]:
        return [n for n, d in self.graph.nodes(data=True) if d.get("kind") == "class"]

    def get_instances(self) -> list[str]:
        return [n for n, d in self.graph.nodes(data=True) if d.get("kind") == "instance"]

    def get_parents(self, node: str) -> list[str]:
        """Return direct superclasses (targets of subClassOf edges)."""
        parents = []
        for _, target, data in self.graph.out_edges(node, data=True):
            if data.get("relation") == "subClassOf":
                parents.append(target)
        return parents

    def get_children(self, node: str) -> list[str]:
        """Return direct subclasses (sources of subClassOf edges targeting this node)."""
        children = []
        for source, _, data in self.graph.in_edges(node, data=True):
            if data.get("relation") == "subClassOf":
                children.append(source)
        return children

    def get_node_description(self, node: str) -> str:
        return self.graph.nodes[node].get("description", "") if node in self.graph else ""

    def get_node_synonyms(self, node: str) -> list[str]:
        """Return synonyms for a node (classes only)."""
        return list(self.graph.nodes[node].get("synonyms", [])) if node in self.graph else []

    def get_node_source_documents(self, node: str) -> list[str]:
        """Return source documents that contributed to this node."""
        return list(self.graph.nodes[node].get("source_documents", [])) if node in self.graph else []

    def get_edge_source_documents(self, source: str, target: str) -> list[str]:
        """Return source documents for an edge."""
        if not self.graph.has_edge(source, target):
            return []
        return list(self.graph[source][target].get("source_documents", []))

    def has_edge(self, source: str, target: str, relation: str | None = None) -> bool:
        if not self.graph.has_edge(source, target):
            return False
        if relation is None:
            return True
        return self.graph[source][target].get("relation") == relation

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    def merge_from(self, other: "OntologyGraph") -> None:
        """Merge another OntologyGraph into this one (nodes, edges, axioms, data props)."""
        for node, attrs in other.graph.nodes(data=True):
            if node not in self.graph:
                self.graph.add_node(node, **attrs)
            else:
                existing_sources = self.graph.nodes[node].get("source_documents", [])
                new_sources = attrs.get("source_documents", [])
                if new_sources:
                    seen = set(existing_sources)
                    for s in new_sources:
                        if s and s not in seen:
                            existing_sources = list(existing_sources) + [s]
                            seen.add(s)
                    self.graph.nodes[node]["source_documents"] = existing_sources
        for src, tgt, data in other.graph.edges(data=True):
            if not self.graph.has_edge(src, tgt):
                self.graph.add_edge(src, tgt, **data)
            else:
                existing_sources = self.graph[src][tgt].get("source_documents", [])
                new_sources = data.get("source_documents", [])
                if new_sources:
                    seen = set(existing_sources)
                    for s in new_sources:
                        if s and s not in seen:
                            existing_sources = list(existing_sources) + [s]
                            seen.add(s)
                    self.graph[src][tgt]["source_documents"] = existing_sources
        existing_axioms = {str(a) for a in self._axioms}
        for axiom in other._axioms:
            if str(axiom) not in existing_axioms:
                self._axioms.append(axiom)
                existing_axioms.add(str(axiom))
        existing_dps = {str(d) for d in self._data_properties}
        for dp in other._data_properties:
            if str(dp) not in existing_dps:
                self._data_properties.append(dp)
                existing_dps.add(str(dp))

    def get_graph(self) -> nx.DiGraph:
        return self.graph

    def export(self) -> dict[str, Any]:
        """Export as node-link JSON with class/instance counts, axioms, and optional embedding cache."""
        data = nx.node_link_data(self.graph)
        data["axioms"] = self._axioms
        data["data_properties"] = self._data_properties
        edge_count = self.graph.number_of_edges()
        data["stats"] = {
            "classes": len(self.get_classes()),
            "instances": len(self.get_instances()),
            "relations": edge_count,
            "axioms": len(self._axioms),
            "data_properties": len(self._data_properties),
        }
        if self.embedding_cache:
            import numpy as np
            data["embedding_cache"] = {
                name: arr.tolist() if hasattr(arr, "tolist") else list(arr)
                for name, arr in self.embedding_cache.items()
            }
        return data
