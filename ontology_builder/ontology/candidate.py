"""Entity candidate profiles for relation inference.

Aggregates full context per entity from the graph (description, relations,
data properties, co-occurrence) so the LLM receives complete information
instead of fragmented per-chunk snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ontology_builder.storage.graphdb import OntologyGraph


@dataclass
class EntityCandidate:
    """Aggregated profile of an entity for LLM relation inference."""

    name: str
    kind: str  # "class" or "instance"
    type: str  # class_name for instances, parent for classes
    description: str
    synonyms: list[str]
    parent: str
    children: list[str]
    vote_count: int
    chunk_ids: list[int]
    known_relations: list[dict]  # [{"relation": str, "target": str, "type": str}]
    data_properties: dict[str, str]
    co_occurring_entities: list[str]

    def to_prompt_context(self) -> str:
        """Compact natural language summary for LLM prompts."""
        lines = [
            f"Entity: {self.name} ({self.kind}, type: {self.type})",
            f"Description: {self.description}",
        ]
        if self.known_relations:
            rel_str = ", ".join(rel.get("relation", "") + " -> " + rel.get("target", "") for rel in self.known_relations[:10])
            rel_str = rel_str or "none"
            lines.append(f"Known relations: {rel_str}")
        if self.data_properties:
            prop_str = ", ".join(f"{k}: {v}" for k, v in list(self.data_properties.items())[:8])
            lines.append(f"Properties: {prop_str}")
        if self.co_occurring_entities:
            co_str = ", ".join(self.co_occurring_entities[:10])
            if len(self.co_occurring_entities) > 10:
                co_str += f" (+{len(self.co_occurring_entities) - 10} more)"
            lines.append(f"Co-occurs with: {co_str}")
        return "\n".join(lines)


def build_entity_candidates(graph: OntologyGraph) -> dict[str, EntityCandidate]:
    """Build EntityCandidate profiles from the graph for each node.

    Reads node attributes, outgoing edges, data properties, and co-occurrence
    from chunk_ids to assemble full context per entity.
    """
    g = graph.get_graph()
    candidates: dict[str, EntityCandidate] = {}

    # Build chunk_id -> [entity_names] index for co-occurrence
    chunk_to_entities: dict[int, list[str]] = {}
    for node in g.nodes():
        data = g.nodes[node]
        chunk_ids = data.get("chunk_ids") or []
        if isinstance(chunk_ids, list):
            for cid in chunk_ids:
                try:
                    cid_int = int(cid) if not isinstance(cid, int) else cid
                    chunk_to_entities.setdefault(cid_int, []).append(node)
                except (ValueError, TypeError):
                    pass

    for node in g.nodes():
        data = g.nodes[node]
        kind = data.get("kind", "class")
        etype = data.get("type", "Entity")
        desc = data.get("description", "")
        synonyms = data.get("synonyms", []) or []
        if not isinstance(synonyms, list):
            synonyms = []

        # Parent: subClassOf or type edge target
        parent = ""
        for _, target, d in g.out_edges(node, data=True):
            if d.get("relation") in ("subClassOf", "type"):
                parent = target
                break

        # Children: nodes pointing to this via subClassOf
        children = [
            src for src, _, d in g.in_edges(node, data=True)
            if d.get("relation") == "subClassOf"
        ]

        # Vote count and chunk_ids
        chunk_ids = data.get("chunk_ids") or []
        if isinstance(chunk_ids, list):
            chunk_ids = [int(c) if isinstance(c, (int, float)) else c for c in chunk_ids if c is not None]
        else:
            chunk_ids = []
        vote_count = data.get("vote_count") or len(chunk_ids) or 1

        # Known relations
        known_relations: list[dict] = []
        for _, target, d in g.out_edges(node, data=True):
            rel = d.get("relation", "related_to")
            if rel not in ("subClassOf", "type"):
                known_relations.append({
                    "relation": rel,
                    "target": target,
                    "type": d.get("relation_type", ""),
                })

        # Data properties
        data_props: dict[str, str] = {}
        for dp in getattr(graph, "data_properties", []) or []:
            if dp.get("entity") == node:
                data_props[dp.get("attribute", "")] = dp.get("value", "")
        # Also node attributes that look like data props (e.g. from inline instance attributes)
        for k, v in data.items():
            if k not in ("id", "type", "kind", "description", "synonyms", "chunk_ids", "vote_count", "source_documents"):
                if isinstance(v, str) and isinstance(k, str):
                    data_props[k] = v

        # Co-occurring entities
        co_occurring: set[str] = set()
        for cid in chunk_ids:
            for other in chunk_to_entities.get(cid, []):
                if other != node:
                    co_occurring.add(other)
        co_occurring_list = sorted(co_occurring)

        candidates[node] = EntityCandidate(
            name=node,
            kind=kind,
            type=parent or etype,
            description=desc,
            synonyms=synonyms,
            parent=parent,
            children=children,
            vote_count=vote_count,
            chunk_ids=chunk_ids,
            known_relations=known_relations,
            data_properties=data_props,
            co_occurring_entities=co_occurring_list,
        )

    return candidates


def build_cooccurrence_pairs(
    candidates: dict[str, EntityCandidate],
    min_shared_chunks: int = 2,
) -> list[tuple[str, str]]:
    """Return entity pairs that share >= min_shared_chunks chunks, sorted by shared count descending.

    Excludes pairs that already have a known_relation between them.
    """
    pairs_with_count: list[tuple[tuple[str, str], int]] = []
    names = list(candidates.keys())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ca, cb = candidates.get(a), candidates.get(b)
            if not ca or not cb:
                continue

            # Shared chunk count
            set_a = set(ca.chunk_ids)
            set_b = set(cb.chunk_ids)
            shared = len(set_a & set_b)
            if shared < min_shared_chunks:
                continue

            # Exclude if already has known relation
            a_targets = {rel.get("target") for rel in ca.known_relations}
            b_targets = {rel.get("target") for rel in cb.known_relations}
            if b in a_targets or a in b_targets:
                continue

            pairs_with_count.append(((a, b), shared))

    pairs_with_count.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in pairs_with_count]
