"""Graph-of-Thought reasoning: nodes=concepts, edges=relations discovered during KB exploration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 5
DEFAULT_MIN_NEW_CONCEPTS = 0  # Stop when no new concepts added in last step


@dataclass
class ReasoningEdge:
    """A relation between two concepts in the reasoning graph."""

    source: str
    relation: str
    target: str
    evidence: str = ""
    source_ref: str = ""


@dataclass
class ReasoningNode:
    """A concept in the reasoning graph with optional definition."""

    concept: str
    definition: str = ""
    node_type: str = "concept"


class ReasoningGraph:
    """Graph-of-Thought: concepts as nodes, relations as edges.

    Used to accumulate knowledge during multi-step KB exploration.
    """

    def __init__(
        self,
        initial_concepts: list[str] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
    ):
        self.nodes: dict[str, ReasoningNode] = {}
        self.edges: list[ReasoningEdge] = []
        self.step_count = 0
        self.max_steps = max_steps
        self._last_step_new_concepts: set[str] = set()

        if initial_concepts:
            for c in initial_concepts:
                if c and c.strip():
                    norm = c.strip().lower()
                    self.nodes[norm] = ReasoningNode(concept=norm)

    def update(
        self,
        concepts: list[str],
        relations: list[tuple[str, str, str]],
        definitions: dict[str, str] | None = None,
        evidence: dict[tuple[str, str], str] | None = None,
    ) -> None:
        """Add discovered concepts and relations to the graph.

        Args:
            concepts: New or existing concept names.
            relations: List of (source, relation, target) tuples.
            definitions: Optional map concept -> definition.
            evidence: Optional map (source, target) -> evidence string.
        """
        definitions = definitions or {}
        evidence_map = evidence or {}
        def_lower = {k.strip().lower(): v for k, v in definitions.items()}

        new_this_step: set[str] = set()
        for c in concepts:
            if c and str(c).strip():
                norm = str(c).strip().lower()
                if norm not in self.nodes:
                    self.nodes[norm] = ReasoningNode(concept=norm)
                    new_this_step.add(norm)
                if norm in def_lower:
                    self.nodes[norm].definition = def_lower[norm]

        for src, rel, tgt in relations:
            if not (src and rel and tgt):
                continue
            src_n = str(src).strip().lower()
            tgt_n = str(tgt).strip().lower()
            if src_n not in self.nodes:
                self.nodes[src_n] = ReasoningNode(concept=src_n)
                new_this_step.add(src_n)
            if tgt_n not in self.nodes:
                self.nodes[tgt_n] = ReasoningNode(concept=tgt_n)
                new_this_step.add(tgt_n)
            if src_n in def_lower:
                self.nodes[src_n].definition = def_lower[src_n]
            if tgt_n in def_lower:
                self.nodes[tgt_n].definition = def_lower[tgt_n]

            ev = evidence_map.get((src_n, tgt_n), "")
            ref = f"edge:{src_n}-{rel}-{tgt_n}"
            edge = ReasoningEdge(source=src_n, relation=rel, target=tgt_n, evidence=ev, source_ref=ref)
            if not self._has_edge(edge):
                self.edges.append(edge)

        self._last_step_new_concepts = new_this_step
        self.step_count += 1
        logger.debug(
            "[ReasoningGraph] Step %d: +%d concepts, +%d edges, new=%s",
            self.step_count,
            len(new_this_step),
            len(relations),
            new_this_step,
        )

    def _has_edge(self, edge: ReasoningEdge) -> bool:
        for e in self.edges:
            if e.source == edge.source and e.relation == edge.relation and e.target == edge.target:
                return True
        return False

    def complete(self) -> bool:
        """Return True if exploration should stop.

        Heuristics:
        - Reached max steps.
        - No new concepts in last step (saturation).
        """
        if self.step_count >= self.max_steps:
            return True
        if self.step_count > 0 and not self._last_step_new_concepts:
            return True
        return False

    def to_context_string(self) -> str:
        """Build a context string from the graph for answer synthesis."""
        lines: list[str] = []
        for node in self.nodes.values():
            if node.definition:
                lines.append(f"{node.concept}: {node.definition}")
            else:
                lines.append(f"Concept: {node.concept}")

        for e in self.edges:
            fact = f"{e.source} --[{e.relation}]--> {e.target}"
            if e.evidence:
                fact += f" | Evidence: {e.evidence}"
            lines.append(fact)

        return "\n".join(lines) if lines else ""

    def to_dict(self) -> dict[str, Any]:
        """Export graph for logging/serialization."""
        return {
            "nodes": [
                {"concept": n.concept, "definition": n.definition, "type": n.node_type}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "relation": e.relation, "target": e.target, "evidence": e.evidence}
                for e in self.edges
            ],
            "step_count": self.step_count,
        }
