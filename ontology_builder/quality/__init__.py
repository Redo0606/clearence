"""Ontology quality metrics and enrichment (Fernández et al. structural reliability)."""

from ontology_builder.quality.report import OntologyQualityReport
from ontology_builder.quality.structural_scorer import (
    StructuralMetrics,
    ReliabilityScore,
    compute_structural_metrics,
    compute_reliability_score,
)
from ontology_builder.quality.relation_evaluator import (
    RelationScore,
    evaluate_relation_correctness,
    get_low_confidence_relations,
)
from ontology_builder.quality.consistency_checker import (
    ConsistencyReport,
    check_relation_consistency,
)
from ontology_builder.quality.hierarchy_enricher import enrich_hierarchy
from ontology_builder.quality.population_booster import boost_population

__all__ = [
    "OntologyQualityReport",
    "StructuralMetrics",
    "ReliabilityScore",
    "compute_structural_metrics",
    "compute_reliability_score",
    "RelationScore",
    "evaluate_relation_correctness",
    "get_low_confidence_relations",
    "ConsistencyReport",
    "check_relation_consistency",
    "enrich_hierarchy",
    "boost_population",
]
