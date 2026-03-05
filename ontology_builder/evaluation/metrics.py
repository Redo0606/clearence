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


def entity_recall(ground_truth_entities: set[str], context_facts: list[str]) -> float:
    """Proportion of ground-truth entities mentioned in the retrieved context."""
    if not ground_truth_entities:
        return 1.0
    context_joined = " ".join(context_facts).lower()
    found = sum(1 for e in ground_truth_entities if e.lower() in context_joined)
    return found / len(ground_truth_entities)


def answer_correctness(predicted_answer: str, reference_answer: str) -> float:
    """Token-level F1 between predicted and reference answers."""
    pred_tokens = set(predicted_answer.lower().split())
    ref_tokens = set(reference_answer.lower().split())
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0
    tp = len(pred_tokens & ref_tokens)
    p = tp / len(pred_tokens)
    r = tp / len(ref_tokens)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


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
