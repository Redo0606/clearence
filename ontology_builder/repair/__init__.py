"""Graph repair: infer missing edges to reduce orphans and bridge components."""

from ontology_builder.repair.repairer import (
    GraphHealthReport,
    RepairConfig,
    RepairReport,
    repair_graph,
    repair_graph_incremental,
)
from ontology_builder.repair.gap_repair import (
    GapRepairReport,
    detect_gaps_in_graph,
    reify_definitions_from_web,
)

__all__ = [
    "GraphHealthReport",
    "RepairConfig",
    "RepairReport",
    "repair_graph",
    "repair_graph_incremental",
    "GapRepairReport",
    "detect_gaps_in_graph",
    "reify_definitions_from_web",
]
