"""Relation correctness scoring: cross-chunk votes and derivation path (Fernández et al.)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.config import get_settings
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

RELATION_EVALUATOR_BATCH_SIZE = 500


@dataclass
class RelationScore:
    """Per-edge correctness signal."""

    source: str
    relation: str
    target: str
    cross_chunk_votes: int
    avg_confidence: float
    derivation_path_length: int
    correctness_score: float


def _derivation_path_length(provenance: dict | None) -> int:
    """1 if direct extraction, >1 if inferred (reasoning chain)."""
    if not provenance:
        return 1
    origin = provenance.get("origin", "")
    rule = provenance.get("rule", "")
    if origin == "extraction":
        return 1
    if origin == "inference_owl" and rule:
        return 2
    if origin == "inference_llm":
        return 2
    if origin == "repair":
        return 2
    return 1


def evaluate_relation_correctness(graph: OntologyGraph) -> list[RelationScore]:
    """Score each unique (source, relation, target) by cross-chunk votes and path length.

    Uses stored vote_count and chunk_ids on edges when present (from pipeline aggregation);
    otherwise falls back to provenance.chunk_id. Writes correctness_score in batches.
    """
    g = graph.get_graph()
    batch_size = getattr(get_settings(), "graph_write_batch_size", None) or RELATION_EVALUATOR_BATCH_SIZE
    edges_with_data = list(g.edges(data=True))
    result: list[RelationScore] = []

    for start in range(0, len(edges_with_data), batch_size):
        batch = edges_with_data[start : start + batch_size]
        for u, v, data in batch:
            r = data.get("relation", "related_to")
            key = (u, r, v)
            # Prefer stored vote_count / chunk_ids from aggregation
            stored_votes = data.get("vote_count")
            stored_chunk_ids = data.get("chunk_ids")
            if stored_votes is not None and stored_votes > 0:
                votes = int(stored_votes)
            elif stored_chunk_ids:
                votes = len(stored_chunk_ids)
            else:
                prov = data.get("provenance") or {}
                chunk_id = prov.get("chunk_id")
                votes = 1 if chunk_id is None else len({int(chunk_id)})
            if votes == 0:
                votes = 1
            conf = float(data.get("confidence", 1.0))
            prov = data.get("provenance") or {}
            path_len = _derivation_path_length(prov)
            norm_votes = min(1.0, votes / 5.0)
            path_score = 1.0 / path_len if path_len else 1.0
            correctness = 0.5 * norm_votes + 0.3 * conf + 0.2 * path_score
            correctness = min(1.0, correctness)
            rs = RelationScore(
                source=u,
                relation=r,
                target=v,
                cross_chunk_votes=votes,
                avg_confidence=conf,
                derivation_path_length=path_len,
                correctness_score=correctness,
            )
            result.append(rs)
            g[u][v]["correctness_score"] = correctness
            g[u][v]["cross_chunk_votes"] = votes
            g[u][v]["derivation_path_length"] = path_len

    return result


def get_low_confidence_relations(
    graph: OntologyGraph,
    threshold: float = 0.3,
) -> list[tuple[str, str, str]]:
    """Return edges with correctness_score below threshold (for debugging)."""
    g = graph.get_graph()
    out: list[tuple[str, str, str]] = []
    for u, v, data in g.edges(data=True):
        score = data.get("correctness_score")
        if score is None:
            continue
        if score < threshold:
            out.append((u, data.get("relation", "related_to"), v))
    return out
