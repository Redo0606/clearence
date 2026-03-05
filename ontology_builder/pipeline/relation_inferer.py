"""LLM-based inference of additional relations from the current graph. Filters by confidence threshold."""

import json
import logging
import re

from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.llm.prompts import INFERENCE_PROMPT
from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5


def infer_relations(graph: OntologyGraph) -> list[dict]:
    """Use LLM to infer additional relations from the current graph.

    Filters by CONFIDENCE_THRESHOLD (0.5). Returns only relations with
    source, target, and confidence >= threshold.

    Args:
        graph: Current ontology graph.

    Returns:
        List of relation dicts (source, relation, target, confidence).
    """
    nodes = graph.get_graph().number_of_nodes()
    edges = graph.get_graph().number_of_edges()
    logger.info("[RelationInferer] Starting | nodes=%d | edges=%d | confidence_threshold=%.2f", nodes, edges, CONFIDENCE_THRESHOLD)

    try:
        graph_data = graph.export()
        graph_text = json.dumps(graph_data, indent=2)
        # Truncate if too large for 4K context models
        max_graph_chars = 3000
        if len(graph_text) > max_graph_chars:
            graph_text = graph_text[:max_graph_chars] + "\n... [truncated for context]"
            logger.warning("[RelationInferer] Truncated graph to %d chars for context", max_graph_chars)
        logger.debug("[RelationInferer] Graph serialized | json_len=%d", len(graph_text))
    except Exception as e:
        logger.warning("[RelationInferer] Failed to export graph | error=%s", e)
        graph_text = "Graph unavailable"

    try:
        logger.debug("[RelationInferer] Calling LLM for inference")
        response = call_llm(
            system="You perform ontology reasoning. Output only valid JSON.",
            user=INFERENCE_PROMPT + graph_text,
        )
    except Exception as e:
        logger.warning("[RelationInferer] LLM call failed | error=%s", e)
        return []

    content = (response or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("[RelationInferer] Invalid JSON | error=%s", e)
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
    logger.info("[RelationInferer] Complete | raw_relations=%d | above_threshold=%d", len(relations), len(result))
    return result
