"""Cross-relation consistency check (Oᵣ/Oₙᵣ discrimination)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


@dataclass
class ConflictRecord:
    """Single conflict with suggested resolution."""

    conflict_type: str
    entity_a: str
    entity_b: str
    relation_a: str = ""
    relation_b: str = ""
    severity: str = "WARNING"
    suggested_resolution: str = ""


@dataclass
class ConsistencyReport:
    """Result of consistency check."""

    critical_conflicts: list[ConflictRecord] = field(default_factory=list)
    warning_conflicts: list[ConflictRecord] = field(default_factory=list)
    is_consistent: bool = True


def check_relation_consistency(graph: OntologyGraph) -> ConsistencyReport:
    """Detect subclass-disjoint, circular subsumption, sibling-subclass, asymmetric violations."""
    g = graph.get_graph()
    report = ConsistencyReport()

    # SubClassOf edges
    subclass: set[tuple[str, str]] = set()
    for u, v, data in g.edges(data=True):
        if data.get("relation") == "subClassOf":
            subclass.add((u, v))

    # Disjointness axioms
    disjoint_pairs: set[tuple[str, str]] = set()
    for axiom in graph.axioms:
        if axiom.get("axiom_type") == "disjointness":
            entities = axiom.get("entities", [])
            if len(entities) >= 2:
                a, b = entities[0], entities[1]
                disjoint_pairs.add((a, b))
                disjoint_pairs.add((b, a))

    # Asymmetric relations from axioms
    asymmetric_relations: set[str] = set()
    for axiom in graph.axioms:
        if axiom.get("axiom_type") == "asymmetry":
            entities = axiom.get("entities", [])
            if entities:
                asymmetric_relations.add(entities[0])

    # Parents per node (for subClassOf)
    parents: dict[str, set[str]] = {}
    for u, v in subclass:
        parents.setdefault(u, set()).add(v)

    # 1. Subclass-disjoint conflict
    for a, b in disjoint_pairs:
        if (a, b) in subclass or (b, a) in subclass:
            report.critical_conflicts.append(ConflictRecord(
                conflict_type="Subclass–Disjoint Conflict",
                entity_a=a,
                entity_b=b,
                relation_a="subClassOf",
                relation_b="disjointWith",
                severity="CRITICAL",
                suggested_resolution=f"Remove either subClassOf({a},{b}) or the disjointness axiom between {a} and {b}.",
            ))

    # 2. Circular subsumption: A subClassOf B and B subClassOf A
    for u, v in subclass:
        if (v, u) in subclass and u != v:
            report.critical_conflicts.append(ConflictRecord(
                conflict_type="Subclass–Superclass Flip",
                entity_a=u,
                entity_b=v,
                relation_a="subClassOf",
                relation_b="subClassOf",
                severity="CRITICAL",
                suggested_resolution=f"Remove one of subClassOf({u},{v}) or subClassOf({v},{u}).",
            ))

    # 3. Sibling-subclass: A subClassOf B but A and B share same parent (siblings)
    for u, v in subclass:
        pa = parents.get(u, set())
        pb = parents.get(v, set())
        common = pa & pb
        if common:
            report.warning_conflicts.append(ConflictRecord(
                conflict_type="Sibling–Subclass Conflict",
                entity_a=u,
                entity_b=v,
                relation_a="subClassOf",
                relation_b="same_parent",
                severity="WARNING",
                suggested_resolution=f"{u} and {v} are in a subclass relationship but share parent(s) {common}; consider clarifying hierarchy.",
            ))

    # 4. Asymmetric relation violation: (A, rel, B) and (B, rel, A) with rel asymmetric
    for u, v, data in g.edges(data=True):
        r = data.get("relation", "")
        if r not in asymmetric_relations:
            continue
        if g.has_edge(v, u):
            ed = g[v][u]
            if ed.get("relation") == r:
                report.warning_conflicts.append(ConflictRecord(
                    conflict_type="Asymmetric Relation Violation",
                    entity_a=u,
                    entity_b=v,
                    relation_a=r,
                    relation_b=r,
                    severity="WARNING",
                    suggested_resolution=f"Relation {r} is asymmetric; remove either ({u},{r},{v}) or ({v},{r},{u}).",
                ))

    report.is_consistent = len(report.critical_conflicts) == 0
    return report
