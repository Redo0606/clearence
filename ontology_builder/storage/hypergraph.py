"""OG-RAG hypergraph construction (Algorithm 1).

Converts an OntologyGraph's factual blocks into a hypergraph H = (N, E) where:
  - N is a set of hypernodes, each a (key, value) pair
  - E is a set of hyperedges, each a frozenset of hypernode indices
    representing co-occurring facts from a single factual block

The flatten step recursively expands nested ontology relationships into
atomic (key, value) pairs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HyperNode:
    """A single atomic fact: (key, value)."""

    key: str
    value: str
    full: str = ""

    def __hash__(self) -> int:
        return hash((self.key, self.value))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HyperNode):
            return NotImplemented
        return self.key == other.key and self.value == other.value


@dataclass
class HyperGraph:
    """Hypergraph H = (N, E) over ontology facts."""

    nodes: list[HyperNode] = field(default_factory=list)
    edges: list[frozenset[int]] = field(default_factory=list)

    _node_index: dict[tuple[str, str], int] = field(default_factory=dict, repr=False)

    def add_node(self, key: str, value: str, full: str = "") -> int:
        """Add a hypernode (or return existing index)."""
        lookup = (key, value)
        if lookup in self._node_index:
            return self._node_index[lookup]
        idx = len(self.nodes)
        self.nodes.append(HyperNode(key=key, value=value, full=full))
        self._node_index[lookup] = idx
        return idx

    def add_edge(self, node_indices: frozenset[int]) -> None:
        if len(node_indices) > 0:
            self.edges.append(node_indices)


def flatten_factual_block(block: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Recursively flatten a factual block into atomic (key, value, full) triples.

    A factual block has ``subject`` and ``attributes`` (list of dicts with
    relation, target, key, value, full).
    """
    triples: list[tuple[str, str, str]] = []
    subject = block.get("subject", "")
    for attr in block.get("attributes", []):
        key = attr.get("key", f"{subject}: {attr.get('relation', '')}")
        value = attr.get("value", attr.get("target", ""))
        full = attr.get("full", f"{key} -> {value}")
        triples.append((key, value, full))
    return triples


def build_hypergraph(factual_blocks: list[dict[str, Any]]) -> HyperGraph:
    """OG-RAG Algorithm 1: Build hypergraph from factual blocks.

    For each factual block:
      1. Flatten into atomic (key, value) pairs
      2. Create hypernodes for each pair
      3. Create a hyperedge linking all hypernodes from that block
    """
    hg = HyperGraph()

    for block in factual_blocks:
        triples = flatten_factual_block(block)
        if not triples:
            continue
        indices: set[int] = set()
        for key, value, full in triples:
            idx = hg.add_node(key, value, full)
            indices.add(idx)
        if indices:
            hg.add_edge(frozenset(indices))

    logger.info(
        "[HyperGraph] Built | nodes=%d | edges=%d",
        len(hg.nodes),
        len(hg.edges),
    )
    return hg
