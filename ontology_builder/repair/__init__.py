"""Graph repair: infer missing edges to reduce orphans and bridge components."""

from ontology_builder.repair.repairer import (
    RepairConfig,
    RepairReport,
    repair_graph,
)

__all__ = ["RepairConfig", "RepairReport", "repair_graph"]
