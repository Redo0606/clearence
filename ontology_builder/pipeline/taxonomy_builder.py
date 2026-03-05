"""Taxonomy builder following OntoGen's 3-stage pipeline (Section 4).

After per-chunk extraction, this module:
  1. Collects all classes across chunks and deduplicates
  2. Prompts LLM to organize them into a taxonomic is-a hierarchy
  3. Applies a grounding check to filter hallucinated entries
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.llm.prompts import TAXONOMY_SYSTEM, TAXONOMY_USER
from ontology_builder.ontology.schema import OntologyClass

logger = logging.getLogger(__name__)


def _deduplicate_classes(classes: list[OntologyClass]) -> list[OntologyClass]:
    """Merge classes with the same (case-insensitive) name, keeping the richer entry."""
    seen: dict[str, OntologyClass] = {}
    for cls in classes:
        key = cls.name.strip().lower()
        if key in seen:
            existing = seen[key]
            if len(cls.description) > len(existing.description):
                seen[key] = cls
            if cls.parent and not existing.parent:
                seen[key] = cls.model_copy(update={"description": max(cls.description, existing.description, key=len)})
        else:
            seen[key] = cls
    return list(seen.values())


def _grounding_check(
    classes: list[dict],
    source_text: str,
    threshold: float = 0.6,
) -> list[dict]:
    """Filter out classes whose name cannot be fuzzy-matched in the source text.

    Uses SequenceMatcher ratio against sliding windows of the lowered source.
    """
    if not source_text:
        return classes
    source_lower = source_text.lower()
    grounded: list[dict] = []
    for cls in classes:
        name = cls.get("name", "").lower()
        if not name:
            continue
        if name in source_lower:
            grounded.append(cls)
            continue
        tokens = name.split()
        if any(t in source_lower for t in tokens if len(t) > 3):
            grounded.append(cls)
            continue
        ratio = SequenceMatcher(None, name, source_lower).ratio()
        if ratio >= threshold:
            grounded.append(cls)
        else:
            logger.debug("[Taxonomy] Filtered ungrounded class: %s (ratio=%.2f)", cls.get("name"), ratio)
    return grounded


def build_taxonomy(
    classes: list[OntologyClass],
    source_text: str = "",
) -> list[OntologyClass]:
    """Organize a flat list of classes into a taxonomic hierarchy via LLM.

    Args:
        classes: Deduplicated classes from all chunks.
        source_text: Full document text for grounding check.

    Returns:
        Classes with updated ``parent`` fields forming a hierarchy.
    """
    classes = _deduplicate_classes(classes)
    if len(classes) <= 1:
        return classes

    class_names = [c.name for c in classes]
    classes_json = json.dumps([{"name": c.name, "description": c.description} for c in classes])
    prompt = TAXONOMY_USER.format(classes_json=classes_json)

    logger.info("[Taxonomy] Organizing %d classes into hierarchy", len(classes))
    try:
        raw = call_llm(system=TAXONOMY_SYSTEM, user=prompt)
    except Exception as e:
        logger.warning("[Taxonomy] LLM call failed: %s — returning flat list", e)
        return classes

    content = (raw or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("[Taxonomy] Invalid JSON from LLM")
        return classes

    taxonomy_raw = data.get("taxonomy", [])
    if not isinstance(taxonomy_raw, list):
        return classes

    taxonomy_raw = _grounding_check(taxonomy_raw, source_text)

    name_to_parent: dict[str, str | None] = {}
    for entry in taxonomy_raw:
        name = entry.get("name", "")
        parent = entry.get("parent")
        if parent and parent not in class_names:
            parent = None
        if name == parent:
            parent = None
        name_to_parent[name] = parent

    result: list[OntologyClass] = []
    for cls in classes:
        parent = name_to_parent.get(cls.name, cls.parent)
        result.append(cls.model_copy(update={"parent": parent}))

    logger.info(
        "[Taxonomy] Hierarchy built: %d classes, %d with parents",
        len(result),
        sum(1 for c in result if c.parent),
    )
    return result
