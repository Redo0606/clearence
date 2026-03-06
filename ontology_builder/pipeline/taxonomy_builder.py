"""Taxonomy builder following OntoGen's 3-stage pipeline (Section 4).

After per-chunk extraction, this module:
  1. Collects all classes across chunks and deduplicates
  2. Prompts LLM to organize them into a taxonomic is-a hierarchy (batched for large class sets)
  3. Applies a grounding check to filter hallucinated entries
"""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher

from core.config import get_settings
from ontology_builder.llm.json_repair import repair_json
from ontology_builder.llm.client import complete
from ontology_builder.llm.prompts import TAXONOMY_SYSTEM, TAXONOMY_USER
from ontology_builder.ontology.schema import OntologyClass

logger = logging.getLogger(__name__)

TAXONOMY_RECONCILIATION_USER = """\
These are the top-level (root) classes from batched taxonomy building. Unify them under a coherent top-level hierarchy.

Root class names (one per batch): {roots_json}

Return a JSON object with at most 10 roots, each optionally with a single parent among the others or null:
{{
  "roots": [
    {{ "name": "<ClassName>", "parent": "<ParentClassName or null>" }}
  ]
}}
"""


def _deduplicate_classes(classes: list[OntologyClass]) -> list[OntologyClass]:
    """Merge classes with the same (case-insensitive) name, keeping the richer entry.

    When merging duplicates: prefer the one with a parent (taxonomy info); merge
    descriptions (keep longest) and synonyms (union). More information => richer concept.
    """
    seen: dict[str, OntologyClass] = {}
    for cls in classes:
        key = cls.name.strip().lower()
        if key in seen:
            existing = seen[key]
            # Prefer parent when one has it
            use_parent = cls.parent if cls.parent else existing.parent
            # Merge description: keep longer
            merged_desc = max(
                (cls.description or "").strip(),
                (existing.description or "").strip(),
                key=len,
            )
            # Merge synonyms: union, deduplicated
            all_synonyms = list(
                dict.fromkeys(
                    (existing.synonyms or []) + (cls.synonyms or []),
                )
            )
            # Prefer the one with parent if only one has it; else prefer longer description
            if cls.parent and not existing.parent:
                base = cls
            elif existing.parent and not cls.parent:
                base = existing
            else:
                base = cls if len(cls.description or "") >= len(existing.description or "") else existing
            seen[key] = base.model_copy(
                update={
                    "parent": use_parent or base.parent,
                    "description": merged_desc or base.description,
                    "synonyms": all_synonyms or (base.synonyms or []),
                }
            )
        else:
            seen[key] = cls
    return list(seen.values())


def _grounding_check(
    classes: list[dict],
    source_text: str,
    threshold: float = 0.6,
) -> list[dict]:
    """Filter out classes whose name cannot be fuzzy-matched in the source text.

    Keeps a class if: (1) name appears in source, (2) any token >3 chars appears,
    or (3) SequenceMatcher ratio >= threshold. Removes hallucinated classes.
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
        # SequenceMatcher ratio against full source; threshold filters hallucinated classes
        ratio = SequenceMatcher(None, name, source_lower).ratio()
        if ratio >= threshold:
            grounded.append(cls)
        else:
            logger.debug("[Taxonomy] Filtered ungrounded class: %s (ratio=%.2f)", cls.get("name"), ratio)
    return grounded


def _batch_taxonomy(
    classes_data: list[dict],
    class_names: list[str],
    batch_size: int | None = None,
) -> dict[str, str | None]:
    """Build taxonomy in batches; merge partial hierarchies. Returns name_to_parent."""
    if batch_size is None:
        batch_size = max(1, get_settings().taxonomy_batch_size)
    max_json_chars = get_settings().llm_max_taxonomy_chars
    name_to_parent: dict[str, str | None] = {}

    for start in range(0, len(classes_data), batch_size):
        batch = classes_data[start : start + batch_size]
        batch_json = json.dumps(batch)
        if len(batch_json) > max_json_chars:
            # Truncate batch to fit
            kept = []
            for c in batch:
                trial = json.dumps(kept + [c])
                if len(trial) <= max_json_chars:
                    kept.append(c)
                else:
                    break
            batch = kept
            batch_json = json.dumps(batch)
        if not batch:
            continue

        prompt = TAXONOMY_USER.format(classes_json=batch_json)
        try:
            raw = complete(system=TAXONOMY_SYSTEM, user=prompt)
        except Exception as e:
            logger.warning("[Taxonomy] Batch LLM call failed: %s", e)
            continue
        try:
            data = repair_json(raw or "")
        except json.JSONDecodeError:
            continue
        taxonomy_raw = data.get("taxonomy", [])
        if not isinstance(taxonomy_raw, list):
            continue
        for entry in taxonomy_raw:
            name = entry.get("name", "")
            parent = entry.get("parent")
            if parent and parent not in class_names:
                parent = None
            if name == parent:
                parent = None
            if name:
                # Prefer assignment with non-null parent when merging
                if name not in name_to_parent or (parent is not None and name_to_parent[name] is None):
                    name_to_parent[name] = parent
    return name_to_parent


def _reconciliation_pass(name_to_parent: dict[str, str | None], class_names: list[str]) -> dict[str, str | None]:
    """Unify top-level roots: one short LLM call to get coherent top-level hierarchy (max 10 roots)."""
    roots = [name for name, parent in name_to_parent.items() if parent is None]
    if len(roots) <= 10:
        return name_to_parent
    roots_json = json.dumps(roots[:20])
    try:
        raw = complete(
            system=TAXONOMY_SYSTEM,
            user=TAXONOMY_RECONCILIATION_USER.format(roots_json=roots_json),
        )
        data = repair_json(raw or "")
        roots_list = data.get("roots", [])
        if isinstance(roots_list, list):
            for entry in roots_list:
                name = entry.get("name", "")
                parent = entry.get("parent")
                if name and name in class_names and (not parent or parent in class_names):
                    name_to_parent[name] = parent if parent else None
    except Exception as e:
        logger.debug("[Taxonomy] Reconciliation pass failed: %s", e)
    return name_to_parent


def build_taxonomy(
    classes: list[OntologyClass],
    source_text: str = "",
) -> list[OntologyClass]:
    """Organize a flat list of classes into a taxonomic hierarchy via LLM.

    For large class sets, uses batched LLM calls and a final reconciliation pass
    for top-level roots. Applies grounding check to merged result.

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
    classes_data = [{"name": c.name, "description": c.description} for c in classes]
    max_json_chars = get_settings().llm_max_taxonomy_chars

    if len(json.dumps(classes_data)) <= max_json_chars:
        # Single call path
        classes_json = json.dumps(classes_data)
        prompt = TAXONOMY_USER.format(classes_json=classes_json)
        logger.info("[Taxonomy] Organizing %d classes into hierarchy (single call)", len(classes))
        try:
            raw = complete(system=TAXONOMY_SYSTEM, user=prompt)
        except Exception as e:
            logger.warning("[Taxonomy] LLM call failed: %s — returning flat list", e)
            return classes
        try:
            data = repair_json(raw or "")
        except json.JSONDecodeError as e:
            logger.warning("[Taxonomy] Invalid JSON from LLM | error=%s", e)
            return classes
        taxonomy_raw = data.get("taxonomy", [])
        if not isinstance(taxonomy_raw, list):
            return classes
        name_to_parent = {}
        for entry in taxonomy_raw:
            name = entry.get("name", "")
            parent = entry.get("parent")
            if parent and parent not in class_names:
                parent = None
            if name == parent:
                parent = None
            if name:
                name_to_parent[name] = parent
    else:
        # Batched path
        logger.info("[Taxonomy] Organizing %d classes into hierarchy (batched)", len(classes))
        name_to_parent = _batch_taxonomy(classes_data, class_names, batch_size=None)
        name_to_parent = _reconciliation_pass(name_to_parent, class_names)

    taxonomy_raw = [{"name": n, "parent": p} for n, p in name_to_parent.items()]
    taxonomy_raw = _grounding_check(taxonomy_raw, source_text)
    name_to_parent = {e["name"]: e.get("parent") for e in taxonomy_raw if e.get("name")}

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
