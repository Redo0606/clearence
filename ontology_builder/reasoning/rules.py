"""
Declarative rule definitions: which relation names are transitive or symmetric.
Aligned with ontology meaning postulates (e.g. reports-to transitive, cooperates-with symmetric).
"""
from typing import Any

# Transitive: if A r B and B r C then infer A r C (e.g. part_of, subclass_of)
TRANSITIVE_RELATIONS = {
    "reports_to",
    "part_of",
    "subclass_of",
    "contains",
    "depends_on",
    "has_part",
    "is_a",
    "related_to",  # often used transitively in taxonomies
}

# Symmetric: if A r B then infer B r A (e.g. related_to, cooperates_with)
SYMMETRIC_RELATIONS = {
    "cooperates_with",
    "related_to",
    "equivalent_to",
    "collaborates_with",
    "works_with",
    "connected_to",
    "associated_with",
}

# Domain-specific: when document subject matches key, add these relations to transitive/symmetric
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
