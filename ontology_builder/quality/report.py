"""Unified quality report for pipeline (Plan 2 P2-8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ontology_builder.quality.structural_scorer import ReliabilityScore, StructuralMetrics
    from ontology_builder.quality.relation_evaluator import RelationScore
    from ontology_builder.quality.consistency_checker import ConsistencyReport


@dataclass
class OntologyQualityReport:
    """Quality dashboard: structural metrics, reliability, relation scores, consistency, actions."""

    structural_metrics: Any = None  # StructuralMetrics
    reliability_score: Any = None   # ReliabilityScore
    relation_scores: list[Any] = field(default_factory=list)  # list[RelationScore], top 20
    consistency_report: Any = None  # ConsistencyReport
    low_quality_warnings: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "low_quality_warnings": self.low_quality_warnings,
            "recommended_actions": self.recommended_actions,
        }
        if self.structural_metrics is not None:
            m = self.structural_metrics
            out["structural_metrics"] = {
                "max_depth": m.max_depth,
                "min_depth": m.min_depth,
                "depth_variance": m.depth_variance,
                "max_breadth": m.max_breadth,
                "breadth_variance": m.breadth_variance,
                "num_classes": m.num_classes,
                "num_instances": m.num_instances,
                "instance_to_class_ratio": m.instance_to_class_ratio,
                "subclass_ratio": m.subclass_ratio,
                "generic_relation_ratio": m.generic_relation_ratio,
                "named_relation_ratio": m.named_relation_ratio,
            }
        if self.reliability_score is not None:
            r = self.reliability_score
            out["reliability_score"] = {"score": r.score, "grade": r.grade, "reasons": r.reasons}
        if self.consistency_report is not None:
            c = self.consistency_report
            out["consistency_report"] = {
                "is_consistent": c.is_consistent,
                "critical_count": len(c.critical_conflicts),
                "warning_count": len(c.warning_conflicts),
                "critical_conflicts": [
                    {
                        "conflict_type": x.conflict_type,
                        "entity_a": x.entity_a,
                        "entity_b": x.entity_b,
                        "relation_a": x.relation_a,
                        "relation_b": x.relation_b,
                        "severity": x.severity,
                        "suggested_resolution": x.suggested_resolution,
                    }
                    for x in c.critical_conflicts
                ],
                "warning_conflicts": [
                    {
                        "conflict_type": x.conflict_type,
                        "entity_a": x.entity_a,
                        "entity_b": x.entity_b,
                        "relation_a": x.relation_a,
                        "relation_b": x.relation_b,
                        "severity": x.severity,
                        "suggested_resolution": x.suggested_resolution,
                    }
                    for x in c.warning_conflicts
                ],
            }
        if self.relation_scores:
            out["relation_scores_top20"] = [
                {
                    "source": rs.source,
                    "relation": rs.relation,
                    "target": rs.target,
                    "correctness_score": rs.correctness_score,
                    "cross_chunk_votes": rs.cross_chunk_votes,
                    "derivation_path_length": rs.derivation_path_length,
                }
                for rs in self.relation_scores[:20]
            ]
        return out
