"""KB Query Engine: wraps graph_index retrieval for agent exploration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ontology_builder.qa.graph_index import (
    RetrievalResult,
    retrieve_hyperedges,
    retrieve_with_context,
)

logger = logging.getLogger(__name__)


@dataclass
class KBQueryResult:
    """Structured result from KB query for agent consumption."""

    concepts: list[str] = field(default_factory=list)
    relations: list[tuple[str, str, str]] = field(default_factory=list)
    definitions: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    ontological_context: str = ""
    facts: list[str] = field(default_factory=list)


def _parse_fact_to_relation(fact: str) -> tuple[str, str, str] | None:
    """Parse 'subject: X, attribute: R, value: Y' into (X, R, Y)."""
    # subject: X, attribute: R, value: Y
    subj = re.search(r"subject:\s*([^,]+)", fact)
    attr = re.search(r"attribute:\s*([^,]+)", fact)
    val = re.search(r"value:\s*([^|]+)", fact)
    if subj and attr and val:
        s = subj.group(1).strip()
        a = attr.group(1).strip()
        v = val.group(1).strip()
        if s and a and v:
            return (s, a, v)
    return None


def _is_valid_concept_name(s: str) -> bool:
    """Filter out values that are not concept names (numbers, descriptions, etc.)."""
    if not s or len(s) > 60:
        return False
    s = s.strip()
    if not s:
        return False
    s_lower = s.lower()
    if re.match(r"^[\d.%]+$", s):
        return False
    if s_lower.startswith(("a ", "an ", "the ", "a type of", "a technique", "a role", "a goal", "a group of", "a designated", "a character", "a player", "a defensive", "ai-controlled", "player-controlled", "equipment or", "goals that", "goals within", "key goals", "key targets", "one of the")):
        return False
    if len(s) > 45 and (" " in s or "," in s):
        return False
    if s_lower in ("e", "100%", "switch aggro"):
        return False
    return True


def _extract_concepts_from_facts(facts: list[str]) -> list[str]:
    """Extract unique concept names from fact strings. Filters out values that are descriptions or numbers."""
    concepts: set[str] = set()
    for fact in facts:
        rel = _parse_fact_to_relation(fact)
        if rel:
            subj, attr, val = rel
            if _is_valid_concept_name(subj):
                concepts.add(subj)
            if _is_valid_concept_name(val) and attr.lower() not in ("description", "health", "effect"):
                concepts.add(val)
    return list(concepts)


def _extract_definitions_from_facts(facts: list[str]) -> dict[str, str]:
    """Extract concept -> definition from facts like 'X: definition' or type facts."""
    definitions: dict[str, str] = {}
    for fact in facts:
        rel = _parse_fact_to_relation(fact)
        if rel:
            subj, attr, val = rel
            if attr.lower() in ("type", "definition", "description"):
                definitions[subj] = val
    return definitions


def query_kb(
    question: str,
    top_k: int = 10,
    use_hyperedges: bool = False,
    max_hyperedges: int = 5,
) -> KBQueryResult:
    """Query the knowledge base and return structured concepts, relations, definitions.

    Args:
        question: Natural language question to retrieve relevant facts.
        top_k: Number of top results for context retrieval.
        use_hyperedges: If True, use hyperedge retrieval instead of context retrieval.
        max_hyperedges: Max hyperedges when use_hyperedges=True.

    Returns:
        KBQueryResult with concepts, relations, definitions, sources.
    """
    if use_hyperedges:
        facts = retrieve_hyperedges(question, k_nodes=top_k, max_hyperedges=max_hyperedges)
        source_refs = [f"he:{i}" for i in range(len(facts))]
        onto_ctx = ""
    else:
        result = retrieve_with_context(question, top_k=top_k)
        facts = result.facts
        source_refs = result.source_refs
        onto_ctx = result.ontological_context

    if not facts:
        return KBQueryResult(ontological_context=onto_ctx)

    concepts = _extract_concepts_from_facts(facts)
    relations: list[tuple[str, str, str]] = []
    for fact in facts:
        rel = _parse_fact_to_relation(fact)
        if rel:
            subj, attr, tgt = rel
            if _is_valid_concept_name(subj) and _is_valid_concept_name(tgt):
                relations.append(rel)

    definitions = _extract_definitions_from_facts(facts)

    return KBQueryResult(
        concepts=concepts,
        relations=relations,
        definitions=definitions,
        sources=facts,
        source_refs=source_refs,
        ontological_context=onto_ctx,
        facts=facts,
    )
