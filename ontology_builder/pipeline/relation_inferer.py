"""LLM-based inference of additional relations from the current graph. Filters by confidence threshold.

Infers multiple elements in parallel: 2 workers for local model, 30 for ChatGPT/gpt-4o-mini.
"""

import json
import logging
import re

from app.config import get_settings
from ontology_builder.llm.client import complete_batch
from ontology_builder.llm.prompts import INFERENCE_PROMPT
from ontology_builder.constants import CONFIDENCE_THRESHOLD
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)


def _get_max_graph_chars() -> int:
    """Return max chars for graph export in LLM context (from settings)."""
    return get_settings().llm_max_graph_chars


def _parse_inferred_relations(content: str) -> list[dict]:
    """Parse LLM response into relation dicts above CONFIDENCE_THRESHOLD.

    Strips markdown fences, parses JSON, filters by confidence and required fields.
    """
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    relations = data.get("relations", [])
    if not isinstance(relations, list):
        return []
    result = []
    for r in relations:
        if not isinstance(r, dict):
            continue
        conf = r.get("confidence", 0.5)
        if conf >= CONFIDENCE_THRESHOLD and r.get("source") and r.get("target"):
            result.append(r)
    return result


def _build_graph_text(graph: OntologyGraph) -> str:
    """Export graph to JSON string, truncated to _get_max_graph_chars() for LLM context."""
    max_chars = _get_max_graph_chars()
    try:
        graph_data = graph.export()
        graph_text = json.dumps(graph_data, indent=2)
        if len(graph_text) > max_chars:
            graph_text = graph_text[:max_chars] + "\n... [truncated for context]"
            logger.warning("[RelationInferer] Truncated graph to %d chars for context", max_chars)
        return graph_text
    except Exception as e:
        logger.warning("[RelationInferer] Failed to export graph | error=%s", e)
        return "Graph unavailable"


def infer_relations(graph: OntologyGraph) -> list[dict]:
    """Use LLM to infer additional relations from the current graph.

    Infers multiple elements in parallel: 2 workers for local model, 30 for ChatGPT/gpt-4o-mini.
    Partitions instances into batches and runs parallel inference.
    Filters by CONFIDENCE_THRESHOLD (0.5). Returns only relations with
    source, target, and confidence >= threshold.

    Args:
        graph: Current ontology graph.

    Returns:
        List of relation dicts (source, relation, target, confidence).
    """
    nodes = graph.get_graph().number_of_nodes()
    edges = graph.get_graph().number_of_edges()
    settings = get_settings()
    workers = settings.get_llm_parallel_workers()
    logger.info(
        "[RelationInferer] Starting | nodes=%d | edges=%d | workers=%d | confidence_threshold=%.2f",
        nodes, edges, workers, CONFIDENCE_THRESHOLD,
    )

    graph_text = _build_graph_text(graph)
    instances = graph.get_instances()
    classes = graph.get_classes()

    # Build inference tasks: partition instances into batches for parallel inference
    if not instances and not classes:
        logger.debug("[RelationInferer] No instances or classes, skipping inference")
        return []

    # Create batches: focus on instances if present, else use classes
    entities = instances if instances else classes
    min_per_batch = max(1, 3)  # at least 3 entities per batch for meaningful inference
    batch_size = max(min_per_batch, (len(entities) + workers - 1) // workers)
    batches: list[list[str]] = []
    for i in range(0, len(entities), batch_size):
        batches.append(entities[i : i + batch_size])

    if not batches:
        batches = [entities[:1]]  # single batch with all if small

    def system_fn(batch: list[str]) -> str:
        return "You perform ontology reasoning. Output only valid JSON."

    def user_fn(batch: list[str]) -> str:
        focus = ", ".join(batch[:10])  # cap focus list length
        if len(batch) > 10:
            focus += f" (and {len(batch) - 10} more)"
        return (
            INFERENCE_PROMPT
            + graph_text
            + f"\n\nFocus on inferring relations involving these entities: {focus}"
        )

    settings = get_settings()
    try:
        responses = complete_batch(
            items=batches,
            system_fn=system_fn,
            user_fn=user_fn,
            parallel=True,
            max_workers=workers,
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
    except Exception as e:
        logger.warning("[RelationInferer] LLM batch inference failed | error=%s", e)
        return []

    # Merge and deduplicate relations from all batches
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []
    for content in responses:
        for r in _parse_inferred_relations(content):
            key = (r.get("source", ""), r.get("relation", ""), r.get("target", ""))
            if key not in seen:
                seen.add(key)
                result.append(r)

    logger.info(
        "[RelationInferer] Complete | batches=%d | inferred_relations=%d",
        len(batches), len(result),
    )
    return result
