"""Graph repair: infer missing edges to reduce orphans and bridge components."""

from ontology_builder.repair.repairer import (
    GraphHealthReport,
    RepairConfig,
    RepairReport,
    repair_graph,
    repair_graph_incremental,
)

__all__ = [
    "GraphHealthReport",
    "RepairConfig",
    "RepairReport",
    "repair_graph",
    "repair_graph_incremental",
]
