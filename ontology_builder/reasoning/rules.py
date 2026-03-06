"""Declarative rule definitions for ontology reasoning.

Combines classic transitive/symmetric sets with OWL 2 RL-style rule
declarations (Smith & Proietti Table 2) and Guarino meaning postulates (O1-O5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Basic relation-name sets (kept for backward compat)
# ---------------------------------------------------------------------------

TRANSITIVE_RELATIONS = {
    "reports_to",
    "part_of",
    "subclass_of",
    "subClassOf",
    "contains",
    "depends_on",
    "has_part",
    "is_a",
}

SYMMETRIC_RELATIONS = {
    "cooperates_with",
    "related_to",
    "equivalent_to",
    "collaborates_with",
    "works_with",
    "connected_to",
    "associated_with",
    "sameAs",
}

DOMAIN_RULES: dict[str, dict[str, Any]] = {
    "human resources": {
        "transitive": {"reports_to"},
        "symmetric": {"cooperates_with", "collaborates_with"},
    },
    "software": {
        "transitive": {"depends_on", "part_of"},
        "symmetric": {"related_to", "connected_to"},
    },
}


# ---------------------------------------------------------------------------
# OWL 2 RL-style rule declarations
# ---------------------------------------------------------------------------

class RuleType(str, Enum):
    TRANSITIVE_SUBSUMPTION = "transitive_subsumption"
    INHERITANCE = "inheritance"
    DOMAIN_PROPAGATION = "domain_propagation"
    RANGE_PROPAGATION = "range_propagation"
    DISJOINTNESS_CHECK = "disjointness_check"
    SYMMETRIC_CLOSURE = "symmetric_closure"
    TRANSITIVE_CLOSURE = "transitive_closure"
    INVERSE_PROPAGATION = "inverse_propagation"


@dataclass(frozen=True)
class InferenceStep:
    """One step of an inference trace — which rule produced which edge."""

    rule: RuleType
    description: str
    source: str
    relation: str
    target: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule.value,
            "description": self.description,
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
        }
