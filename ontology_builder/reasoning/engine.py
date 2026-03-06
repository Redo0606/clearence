"""OWL 2 RL-style reasoning engine with fixpoint iteration and inference tracing.

Implements rules from Smith & Proietti (Table 2) and Guarino meaning postulates:
  - Transitive subsumption: A subClassOf B, B subClassOf C -> A subClassOf C
  - Inheritance: A subClassOf B, x type A -> x type B
  - Domain propagation: property P has domain C, x P y -> x type C
  - Range propagation: property P has range C, x P y -> y type C
  - Disjointness checking: C1 disjointWith C2, x type C1, x type C2 -> violation
  - Symmetric closure: symmetric property
  - Transitive closure: transitive property

All rules iterate until fixpoint (no new inferences). Each inference is
recorded in an ``inference_trace`` for explainability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from ontology_builder.reasoning.rules import (
    DOMAIN_RULES,
    SYMMETRIC_RELATIONS,
    TRANSITIVE_RELATIONS,
    InferenceStep,
    RuleType,
)
from ontology_builder.constants import MAX_REASONING_ITERATIONS
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Outcome of a reasoning pass."""

    inferred_edges: int = 0
    consistency_violations: list[str] = field(default_factory=list)
    inference_trace: list[dict[str, str]] = field(default_factory=list)
    iterations: int = 0


# ---------------------------------------------------------------------------
# Individual OWL 2 RL rules
# ---------------------------------------------------------------------------

def _apply_transitive_subsumption(graph: OntologyGraph, trace: list[InferenceStep]) -> int:
    """If A subClassOf B and B subClassOf C, infer A subClassOf C."""
    g = graph.get_graph()
    edges = [(u, v) for u, v, d in g.edges(data=True) if d.get("relation") == "subClassOf"]
    if not edges:
        return 0
    temp = nx.DiGraph(edges)
    try:
        closure = nx.transitive_closure(temp)
    except Exception:
        return 0
    new_edges = set(closure.edges()) - set(temp.edges())
    added = 0
    for u, v in new_edges:
        if not graph.has_edge(u, v, "subClassOf"):
            graph.add_relation(u, "subClassOf", v, provenance={"origin": "inference_owl", "rule": "transitive_subsumption"})
            step = InferenceStep(
                rule=RuleType.TRANSITIVE_SUBSUMPTION,
                description=f"{u} subClassOf {v} (via transitive subsumption chain)",
                source=u, relation="subClassOf", target=v,
            )
            trace.append(step)
            added += 1
    return added


def _apply_inheritance(graph: OntologyGraph, trace: list[InferenceStep]) -> int:
    """If A subClassOf B and x type A, infer x type B."""
    g = graph.get_graph()
    subclass_map: dict[str, list[str]] = {}
    for u, v, d in g.edges(data=True):
        if d.get("relation") == "subClassOf":
            subclass_map.setdefault(u, []).append(v)

    type_edges: list[tuple[str, str]] = []
    for u, v, d in g.edges(data=True):
        if d.get("relation") == "type":
            type_edges.append((u, v))

    added = 0
    for instance, cls in type_edges:
        for super_cls in subclass_map.get(cls, []):
            if not graph.has_edge(instance, super_cls, "type"):
                graph.add_relation(instance, "type", super_cls, provenance={"origin": "inference_owl", "rule": "inheritance"})
                step = InferenceStep(
                    rule=RuleType.INHERITANCE,
                    description=f"{instance} type {super_cls} (inherited via {cls} subClassOf {super_cls})",
                    source=instance, relation="type", target=super_cls,
                )
                trace.append(step)
                added += 1
    return added


def _apply_domain_range_propagation(graph: OntologyGraph, trace: list[InferenceStep]) -> int:
    """If property P has domain/range in axioms, propagate type assertions."""
    added = 0
    g = graph.get_graph()
    for axiom in graph.axioms:
        atype = axiom.get("axiom_type", "")
        entities = axiom.get("entities", [])

        if atype == "domain" and len(entities) >= 2:
            prop_name, domain_cls = entities[0], entities[1]
            for u, v, d in list(g.edges(data=True)):
                if d.get("relation") == prop_name:
                    if not graph.has_edge(u, domain_cls, "type"):
                        graph.add_relation(u, "type", domain_cls, provenance={"origin": "inference_owl", "rule": "domain_propagation"})
                        trace.append(InferenceStep(
                            rule=RuleType.DOMAIN_PROPAGATION,
                            description=f"{u} type {domain_cls} (domain of {prop_name})",
                            source=u, relation="type", target=domain_cls,
                        ))
                        added += 1

        elif atype == "range" and len(entities) >= 2:
            prop_name, range_cls = entities[0], entities[1]
            for u, v, d in list(g.edges(data=True)):
                if d.get("relation") == prop_name:
                    if not graph.has_edge(v, range_cls, "type"):
                        graph.add_relation(v, "type", range_cls, provenance={"origin": "inference_owl", "rule": "range_propagation"})
                        trace.append(InferenceStep(
                            rule=RuleType.RANGE_PROPAGATION,
                            description=f"{v} type {range_cls} (range of {prop_name})",
                            source=v, relation="type", target=range_cls,
                        ))
                        added += 1
    return added


def _check_disjointness(graph: OntologyGraph, violations: list[str]) -> None:
    """If C1 disjointWith C2, flag any x typed as both."""
    g = graph.get_graph()
    disjoint_pairs: list[tuple[str, str]] = []
    for axiom in graph.axioms:
        if axiom.get("axiom_type") == "disjointness":
            entities = axiom.get("entities", [])
            if len(entities) >= 2:
                disjoint_pairs.append((entities[0], entities[1]))

    if not disjoint_pairs:
        return

    instance_types: dict[str, set[str]] = {}
    for u, v, d in g.edges(data=True):
        if d.get("relation") == "type":
            instance_types.setdefault(u, set()).add(v)

    for c1, c2 in disjoint_pairs:
        for inst, types in instance_types.items():
            if c1 in types and c2 in types:
                msg = f"Consistency violation: {inst} is typed as both {c1} and {c2} (disjoint)"
                violations.append(msg)
                logger.warning("[Reasoning] %s", msg)


def _apply_transitive_closure(graph: OntologyGraph, relation_names: set[str], trace: list[InferenceStep]) -> int:
    """Compute transitive closure for given relations."""
    g = graph.get_graph()
    added = 0
    for r in relation_names:
        if r == "subClassOf":
            continue
        edges_r = [(u, v) for u, v, d in g.edges(data=True) if d.get("relation") == r]
        if not edges_r:
            continue
        temp = nx.DiGraph(edges_r)
        try:
            closure = nx.transitive_closure(temp)
        except Exception:
            continue
        new_edges = set(closure.edges()) - set(temp.edges())
        for u, v in new_edges:
            if not g.has_edge(u, v):
                graph.add_relation(u, r, v, provenance={"origin": "inference_owl", "rule": "transitive_closure"})
                trace.append(InferenceStep(
                    rule=RuleType.TRANSITIVE_CLOSURE,
                    description=f"{u} {r} {v} (transitive closure)",
                    source=u, relation=r, target=v,
                ))
                added += 1
    return added


def _apply_symmetric_closure(graph: OntologyGraph, relation_names: set[str], trace: list[InferenceStep]) -> int:
    """Add reverse edges for symmetric relations."""
    g = graph.get_graph()
    to_add: list[tuple[str, str, str]] = []
    for u, v, d in g.edges(data=True):
        r = d.get("relation")
        if r in relation_names and not g.has_edge(v, u):
            to_add.append((v, u, r))
    for a, b, r in to_add:
        graph.add_relation(a, r, b, provenance={"origin": "inference_owl", "rule": "symmetric_closure"})
        trace.append(InferenceStep(
            rule=RuleType.SYMMETRIC_CLOSURE,
            description=f"{a} {r} {b} (symmetric of {b} {r} {a})",
            source=a, relation=r, target=b,
        ))
    return len(to_add)


def _apply_inverse_propagation(
    graph: OntologyGraph,
    inverse_pairs: list[tuple[str, str]],
    trace: list[InferenceStep],
) -> int:
    """For each (rel1, rel2) inverse pair, add (B, rel2, A) for every (A, rel1, B)."""
    g = graph.get_graph()
    added = 0
    inverse_map: dict[str, str] = {}
    for r1, r2 in inverse_pairs:
        inverse_map[r1] = r2
        inverse_map[r2] = r1
    for u, v, d in list(g.edges(data=True)):
        r = d.get("relation")
        inv = inverse_map.get(r)
        if not inv:
            continue
        if not graph.has_edge(v, u, inv):
            graph.add_relation(v, inv, u, provenance={"origin": "inference_owl", "rule": "inverse_propagation"})
            trace.append(InferenceStep(
                rule=RuleType.INVERSE_PROPAGATION,
                description=f"{v} {inv} {u} (inverse of {u} {r} {v})",
                source=v, relation=inv, target=u,
            ))
            added += 1
    return added


def _axiom_relation_sets(graph: OntologyGraph) -> tuple[set[str], set[str], list[tuple[str, str]]]:
    """Scan graph._axioms for transitivity, symmetry, inverse. Return (transitive, symmetric, inverse_pairs)."""
    transitive: set[str] = set()
    symmetric: set[str] = set()
    inverse_pairs: list[tuple[str, str]] = []
    for axiom in graph.axioms:
        atype = axiom.get("axiom_type") or ""
        entities = axiom.get("entities") or []
        if atype == "transitivity" and len(entities) >= 1:
            transitive.add(entities[0])
        elif atype == "symmetry" and len(entities) >= 1:
            symmetric.add(entities[0])
        elif atype == "inverse" and len(entities) >= 2:
            inverse_pairs.append((entities[0], entities[1]))
    return transitive, symmetric, inverse_pairs


# ---------------------------------------------------------------------------
# Main entry point — fixpoint iteration
# ---------------------------------------------------------------------------

def run_inference(graph: OntologyGraph, subject: str | None = None) -> ReasoningResult:
    """Apply all OWL 2 RL rules until fixpoint (no new inferences).

    Auto-detects transitive/symmetric relations from graph axioms; adds inverse propagation.
    Returns a ``ReasoningResult`` with counts, violations, and full trace.
    """
    result = ReasoningResult()

    transitive = set(TRANSITIVE_RELATIONS)
    symmetric = set(SYMMETRIC_RELATIONS)
    inverse_pairs: list[tuple[str, str]] = []
    # Scan axioms for transitivity, symmetry, inverse (do not mutate module-level constants)
    ax_trans, ax_sym, inverse_pairs = _axiom_relation_sets(graph)
    transitive.update(ax_trans)
    symmetric.update(ax_sym)

    if subject:
        subject_lower = subject.lower().strip()
        for key, rules in DOMAIN_RULES.items():
            if key in subject_lower or subject_lower in key:
                transitive.update(rules.get("transitive", []))
                symmetric.update(rules.get("symmetric", []))
                break

    trace: list[InferenceStep] = []

    logger.info(
        "[Reasoning] Starting OWL 2 RL inference | nodes=%d edges=%d",
        graph.get_graph().number_of_nodes(),
        graph.get_graph().number_of_edges(),
    )

    for iteration in range(1, MAX_REASONING_ITERATIONS + 1):
        added_this_round = 0
        n = _apply_transitive_subsumption(graph, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — transitive_subsumption: %d", iteration, n)
        n = _apply_inheritance(graph, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — inheritance: %d", iteration, n)
        n = _apply_domain_range_propagation(graph, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — domain_range: %d", iteration, n)
        n = _apply_transitive_closure(graph, transitive, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — transitive_closure: %d", iteration, n)
        n = _apply_symmetric_closure(graph, symmetric, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — symmetric_closure: %d", iteration, n)
        n = _apply_inverse_propagation(graph, inverse_pairs, trace)
        added_this_round += n
        if n:
            logger.debug("[Reasoning] Iteration %d — inverse_propagation: %d", iteration, n)

        result.inferred_edges += added_this_round
        result.iterations = iteration

        logger.debug("[Reasoning] Iteration %d — %d new edges total", iteration, added_this_round)

        if added_this_round == 0:
            break

    _check_disjointness(graph, result.consistency_violations)

    result.inference_trace = [s.to_dict() for s in trace]

    logger.info(
        "[Reasoning] Complete | iterations=%d inferred=%d violations=%d",
        result.iterations,
        result.inferred_edges,
        len(result.consistency_violations),
    )
    return result


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

def apply_transitive_closure(graph: OntologyGraph, relation_names: set[str]) -> int:
    """Legacy wrapper — returns count of added edges."""
    trace: list[InferenceStep] = []
    return _apply_transitive_closure(graph, relation_names, trace)


def apply_symmetric_closure(graph: OntologyGraph, relation_names: set[str]) -> int:
    """Legacy wrapper — returns count of added edges."""
    trace: list[InferenceStep] = []
    return _apply_symmetric_closure(graph, relation_names, trace)
