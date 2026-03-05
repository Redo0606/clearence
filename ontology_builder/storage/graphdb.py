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


class OntologyGraph:
    """NetworkX DiGraph wrapper for formal ontology with class/instance nodes and axioms."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._axioms: list[dict[str, Any]] = []
        self._data_properties: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_entity(self, name: str, etype: str, kind: str = "class", **attrs: Any) -> None:
        """Add an entity node.

        Args:
            name: Entity identifier.
            etype: Semantic type label (e.g. "Concept", "Person").
            kind: "class" or "instance".
            **attrs: Extra attributes stored on the node (description, etc.).
        """
        self.graph.add_node(name, type=etype, kind=kind, **attrs)

    def add_class(
        self,
        name: str,
        description: str = "",
        parent: str | None = None,
        synonyms: list[str] | None = None,
        source_document: str | None = None,
    ) -> None:
        attrs: dict[str, Any] = {}
        if synonyms:
            attrs["synonyms"] = list(synonyms)
        if source_document:
            attrs["source_documents"] = _merge_source_documents(
                self.graph.nodes.get(name, {}).get("source_documents", []),
                source_document,
            )
        self.add_entity(name, etype="Class", kind="class", description=description, **attrs)
        if parent:
            self.add_relation(name, "subClassOf", parent, source_document=source_document)

    def add_instance(
        self,
        name: str,
        class_name: str,
        description: str = "",
        source_document: str | None = None,
    ) -> None:
        attrs: dict[str, Any] = {}
        if source_document:
            attrs["source_documents"] = _merge_source_documents(
                self.graph.nodes.get(name, {}).get("source_documents", []),
                source_document,
            )
        self.add_entity(name, etype=class_name, kind="instance", description=description, **attrs)
        if class_name and class_name in self.graph:
            self.add_relation(name, "type", class_name, source_document=source_document)

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
        **attrs: Any,
    ) -> None:
        """Add a directed relation edge with OG-RAG structured fact fields."""
        key_field = f"{source}: {relation}"
        full_field = f"{source}: {relation} -> {target}"
        # Exclude key/value/full from attrs to avoid duplicate kwargs when loading from export
        edge_attrs = {k: v for k, v in attrs.items() if k not in ("key", "value", "full")}
        if source_document:
            if self.graph.has_edge(source, target):
                existing = self.graph[source][target]
                edge_attrs["source_documents"] = _merge_source_documents(
                    existing.get("source_documents", []),
                    source_document,
                )
            else:
                edge_attrs["source_documents"] = _merge_source_documents([], source_document)
        self.graph.add_edge(
            source,
            target,
            relation=relation,
            key=key_field,
            value=target,
            full=full_field,
            confidence=confidence,
            **edge_attrs,
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
        """Export as node-link JSON with class/instance counts and axioms."""
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
        return data
