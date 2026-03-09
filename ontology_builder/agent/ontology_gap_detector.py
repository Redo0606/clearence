"""Detect missing concepts and relations in the knowledge base (ontology gaps)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ontology_builder.agent.graph_reasoner import ReasoningGraph

logger = logging.getLogger(__name__)

MAX_GAPS_TO_REPORT = 10


def _is_noise_concept(concept: str) -> bool:
    """Filter out concepts that are likely noise (values, descriptions, etc.)."""
    if not concept or len(concept) > 50:
        return True
    c = concept.strip().lower()
    if re.match(r"^[\d.%]+$", c):
        return True
    if c in ("e", "100%", "switch aggro", "the game", "middle of the pack"):
        return True
    if c.startswith(("a ", "an ", "the ", "a type of", "a technique", "a role", "a goal", "a group of", "a designated", "a character", "a player", "a defensive", "ai-controlled", "player-controlled", "equipment or", "goals that", "goals within", "key goals", "key targets", "one of the", "minions that")):
        return True
    if len(concept) > 40 and (" " in concept or "," in concept):
        return True
    return False


@dataclass
class OntologyGap:
    """A detected gap in the knowledge base."""

    gap_type: str  # "missing_concept" | "missing_relation"
    subject: str = ""
    relation: str = ""
    target: str = ""
    description: str = ""


def detect_gaps(
    original_query: str,
    graph: ReasoningGraph,
    concepts_without_definitions: list[str] | None = None,
) -> list[OntologyGap]:
    """Detect ontology gaps: concepts referenced but not defined, missing relations.

    Filters noise and caps the number of reported gaps.

    Args:
        original_query: User's original question.
        graph: Current reasoning graph.
        concepts_without_definitions: Optional list of concepts that have no definition.

    Returns:
        List of OntologyGap objects.
    """
    gaps: list[OntologyGap] = []
    seen_normalized: set[str] = set()

    for concept in graph.nodes:
        if _is_noise_concept(concept):
            continue
        node = graph.nodes[concept]
        if not node.definition:
            norm = concept.strip().lower()
            if norm in seen_normalized:
                continue
            seen_normalized.add(norm)
            gaps.append(
                OntologyGap(
                    gap_type="missing_concept",
                    subject=concept,
                    description=f"Missing concept: {concept} (referenced but not defined in KB)",
                )
            )
            if len(gaps) >= MAX_GAPS_TO_REPORT:
                break

    query_lower = original_query.lower()
    if "scale" in query_lower or "scale with" in query_lower:
        for e in graph.edges:
            if "scale" not in e.relation.lower() and "scale" in query_lower:
                gaps.append(
                    OntologyGap(
                        gap_type="missing_relation",
                        subject="Ability",
                        relation="scales_with",
                        target="Item",
                        description="Missing relation: Ability → scales_with → Item (query asks about scaling)",
                    )
                )
                break

    return gaps


def gaps_to_log_string(gaps: list[OntologyGap]) -> str:
    """Format gaps for logging."""
    if not gaps:
        return ""
    lines = []
    for g in gaps:
        if g.gap_type == "missing_concept":
            lines.append(f"Ontology Gap: {g.description}")
        else:
            lines.append(f"Ontology Gap: {g.subject} → {g.relation} → {g.target} ({g.description})")
    return "\n".join(lines)
