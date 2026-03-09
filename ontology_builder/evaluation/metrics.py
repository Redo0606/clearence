"""Evaluation metrics for ontology quality and RAG performance.

Ontology quality (Bakker et al.):
  - Precision, Recall, F1 per component (classes, instances, relations)
  - Average degree score for interconnectedness

RAG quality (OG-RAG / RAGAS-inspired):
  - Context Recall: proportion of ground-truth claims attributable to context
  - Entity Recall: proportion of ground-truth entities found in context
  - Answer Correctness: overlap between predicted and reference answer

Pipeline report:
  - PipelineReport dataclass aggregating extraction stats, timing, reasoning results
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Ontology quality metrics (Bakker)
# ---------------------------------------------------------------------------

@dataclass
class ComponentMetrics:
    """P/R/F1 for one ontology component (classes, instances, or relations)."""

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"precision": self.precision, "recall": self.recall, "f1": self.f1}


def _set_metrics(predicted: set[str], reference: set[str]) -> ComponentMetrics:
    if not predicted and not reference:
        return ComponentMetrics(precision=1.0, recall=1.0, f1=1.0)
    if not predicted:
        return ComponentMetrics(precision=0.0, recall=0.0, f1=0.0)
    if not reference:
        return ComponentMetrics(precision=0.0, recall=0.0, f1=0.0)
    tp = len(predicted & reference)
    p = tp / len(predicted) if predicted else 0.0
    r = tp / len(reference) if reference else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return ComponentMetrics(precision=p, recall=r, f1=f)


def ontology_quality(
    predicted_classes: set[str],
    reference_classes: set[str],
    predicted_instances: set[str],
    reference_instances: set[str],
    predicted_relations: set[tuple[str, str, str]],
    reference_relations: set[tuple[str, str, str]],
    graph_num_edges: int = 0,
    graph_num_nodes: int = 1,
) -> dict[str, Any]:
    """Compute ontology quality metrics.

    Returns dict with class_metrics, instance_metrics, relation_metrics,
    average_degree, and overall_f1.
    """
    cls_m = _set_metrics(predicted_classes, reference_classes)
    inst_m = _set_metrics(predicted_instances, reference_instances)

    pred_rel_norm = {(s.lower(), r.lower(), t.lower()) for s, r, t in predicted_relations}
    ref_rel_norm = {(s.lower(), r.lower(), t.lower()) for s, r, t in reference_relations}
    rel_m = _set_metrics(pred_rel_norm, ref_rel_norm)

    avg_degree = (2 * graph_num_edges / graph_num_nodes) if graph_num_nodes > 0 else 0.0

    overall_f1 = (cls_m.f1 + inst_m.f1 + rel_m.f1) / 3.0

    return {
        "class_metrics": cls_m.to_dict(),
        "instance_metrics": inst_m.to_dict(),
        "relation_metrics": rel_m.to_dict(),
        "average_degree": round(avg_degree, 3),
        "overall_f1": round(overall_f1, 4),
    }


# ---------------------------------------------------------------------------
# RAG quality metrics (RAGAS-inspired)
# ---------------------------------------------------------------------------

def context_recall(ground_truth_claims: list[str], context_facts: list[str]) -> float:
    """Proportion of ground-truth claims that can be found (substring) in context."""
    if not ground_truth_claims:
        return 1.0
    context_joined = " ".join(context_facts).lower()
    found = sum(1 for claim in ground_truth_claims if claim.lower() in context_joined)
    return found / len(ground_truth_claims)


def _split_camel(s: str) -> str:
    """Split CamelCase into space-separated words for flexible matching."""
    import re
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", s).lower()


def entity_recall(ground_truth_entities: set[str], context_facts: list[str]) -> float:
    """Proportion of ground-truth entities (from reference/question) found in retrieved context.

    RAGAS-style: entities come from the reference answer, not from context.
    Supports CamelCase matching: 'TrainerBattle' matches 'trainer battle' in context.
    """
    if not ground_truth_entities:
        return 1.0
    context_joined = " ".join(context_facts).lower()
    found = 0
    for e in ground_truth_entities:
        el = e.lower()
        if el in context_joined:
            found += 1
        elif _split_camel(e) in context_joined:
            found += 1
    return found / len(ground_truth_entities)


def answer_correctness(predicted_answer: str, reference_answer: str) -> float:
    """Token-level F1 between predicted and reference answers.

    Filters stopwords to avoid inflation from common words. Uses normalized tokens
    (alphanumeric) for fair comparison.
    """
    pred_tokens = [
        _normalize_token(t) for t in predicted_answer.lower().split()
        if _normalize_token(t) and _normalize_token(t) not in _STOPWORDS
    ]
    ref_tokens = [
        _normalize_token(t) for t in reference_answer.lower().split()
        if _normalize_token(t) and _normalize_token(t) not in _STOPWORDS
    ]
    pred_set = set(t for t in pred_tokens if len(t) > 1)
    ref_set = set(t for t in ref_tokens if len(t) > 1)
    if not pred_set and not ref_set:
        return 1.0
    if not ref_set:
        return 0.0
    tp = len(pred_set & ref_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(ref_set)
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def _normalize_token(t: str) -> str:
    """Strip punctuation for token overlap."""
    return "".join(c for c in t.lower() if c.isalnum() or c.isspace()).strip()


# Stopwords that inflate answer_correctness when not filtered
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of with by from as is are was were be been being have has had do does did will would could should may might must can shall".split()
)


def _token_supported_in_context(token: str, context_tokens: set[str], context_joined: str) -> bool:
    """True if token appears in context (exact or as substring for compound words)."""
    if token in context_tokens:
        return True
    return token in context_joined


def context_recall_relaxed(ground_truth_claims: list[str], context_facts: list[str]) -> float:
    """Proportion of reference claims supported by retrieved context.

    RAGAS-style: each claim must be attributable to context. Uses strict token overlap
    (≥75%) to avoid false positives. Supports substring match for compound words
    (e.g. 'effectiveness' in 'typeeffectiveness'). Trivial claims (< 3 tokens) excluded.
    """
    if not ground_truth_claims:
        return 1.0
    context_joined = " ".join(context_facts).lower()
    context_tokens = set(_normalize_token(t) for t in context_joined.split() if len(_normalize_token(t)) > 1)
    supported = 0
    counted = 0
    for claim in ground_truth_claims:
        claim_tokens = [t for t in _normalize_token(claim).split() if len(t) > 1 and t not in _STOPWORDS]
        if len(claim_tokens) < 3:
            continue
        counted += 1
        overlap = sum(
            1 for t in claim_tokens
            if _token_supported_in_context(t, context_tokens, context_joined)
        )
        if overlap >= 0.75 * len(claim_tokens):
            supported += 1
    if counted == 0:
        return 1.0
    return supported / counted


# ---------------------------------------------------------------------------
# Pipeline report
# ---------------------------------------------------------------------------

@dataclass
class ChunkStats:
    """Extraction stats for a single chunk."""

    chunk_index: int = 0
    chunk_length: int = 0
    classes_extracted: int = 0
    instances_extracted: int = 0
    relations_extracted: int = 0
    axioms_extracted: int = 0


@dataclass
class PipelineReport:
    """Aggregated report from a full pipeline run."""

    document_path: str = ""
    total_chunks: int = 0
    chunk_stats: list[ChunkStats] = field(default_factory=list)

    total_classes: int = 0
    total_instances: int = 0
    total_relations: int = 0
    total_axioms: int = 0
    total_data_properties: int = 0

    # After merge, before LLM inference (for step-by-step display)
    extraction_classes: int = 0
    extraction_instances: int = 0
    extraction_relations: int = 0
    extraction_axioms: int = 0
    llm_inferred_relations: int = 0

    reasoning_inferred_edges: int = 0
    reasoning_iterations: int = 0
    consistency_violations: list[str] = field(default_factory=list)

    elapsed_seconds: float = 0.0
    extraction_mode: str = "sequential"
    quality: Any = None  # OntologyQualityReport (Plan 2 P2-8)

    # Quality gate: when merge was skipped because extraction failed min quality threshold
    merge_skipped: bool = False
    merge_skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_path": self.document_path,
            "total_chunks": self.total_chunks,
            "chunk_stats": [
                {
                    "chunk_index": cs.chunk_index,
                    "chunk_length": cs.chunk_length,
                    "classes": cs.classes_extracted,
                    "instances": cs.instances_extracted,
                    "relations": cs.relations_extracted,
                    "axioms": cs.axioms_extracted,
                }
                for cs in self.chunk_stats
            ],
            "totals": {
                "classes": self.total_classes,
                "instances": self.total_instances,
                "relations": self.total_relations,
                "axioms": self.total_axioms,
                "data_properties": self.total_data_properties,
            },
            "extraction_totals": {
                "classes": self.extraction_classes,
                "instances": self.extraction_instances,
                "relations": self.extraction_relations,
                "axioms": self.extraction_axioms,
            },
            "llm_inferred_relations": self.llm_inferred_relations,
            "reasoning": {
                "inferred_edges": self.reasoning_inferred_edges,
                "iterations": self.reasoning_iterations,
                "consistency_violations": self.consistency_violations,
            },
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "extraction_mode": self.extraction_mode,
            "quality": self.quality.to_dict() if self.quality is not None and hasattr(self.quality, "to_dict") else None,
            "merge_skipped": self.merge_skipped,
            "merge_skip_reason": self.merge_skip_reason,
        }


class PipelineTimer:
    """Simple context manager for timing pipeline stages."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "PipelineTimer":
        self._start = time.time()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.time() - self._start
