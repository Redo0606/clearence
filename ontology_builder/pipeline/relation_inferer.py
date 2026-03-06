"""LLM-based inference of additional relations from the current graph. Filters by confidence threshold.

Infers multiple elements in parallel: 2 workers for local model, 30 for ChatGPT/gpt-4o-mini.
"""

import json
import logging
import re

import networkx as nx

from core.config import get_settings
from ontology_builder.llm.client import complete, complete_batch
from ontology_builder.llm.prompts import CROSS_COMPONENT_INFERENCE_PROMPT, INFERENCE_PROMPT
from ontology_builder.constants import CONFIDENCE_THRESHOLD
from ontology_builder.storage.graphdb import OntologyGraph


def _get_confidence_threshold() -> float:
    s = get_settings()
    return s.confidence_threshold if s.confidence_threshold is not None else CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

CROSS_COMPONENT_MAX_PAIRS = 30


def _get_max_graph_chars() -> int:
    """Return max chars for graph export in LLM context (from settings)."""
    return get_settings().llm_max_graph_chars


def _stratify_batches_by_component(
    entities: list[str],
    node_to_component: dict[str, int],
    batch_size: int,
    num_components: int,
) -> list[list[str]]:
    """Build batches that mix entities from different components when possible."""
    if num_components <= 1 or not node_to_component:
        batches = []
        for i in range(0, len(entities), batch_size):
            batches.append(entities[i : i + batch_size])
        return batches

    # Group entities by component
    by_comp: dict[int, list[str]] = {}
    for e in entities:
        c = node_to_component.get(e, 0)
        by_comp.setdefault(c, []).append(e)
    comp_lists = list(by_comp.values())

    # Round-robin interleave so each batch gets entities from multiple components
    interleaved: list[str] = []
    indices = [0] * len(comp_lists)
    while True:
        added = 0
        for i, comp_entities in enumerate(comp_lists):
            if indices[i] < len(comp_entities):
                interleaved.append(comp_entities[indices[i]])
                indices[i] += 1
                added += 1
        if added == 0:
            break

    batches = []
    for i in range(0, len(interleaved), batch_size):
        batches.append(interleaved[i : i + batch_size])
    return batches


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
    threshold = _get_confidence_threshold()
    result = []
    for r in relations:
        if not isinstance(r, dict):
            continue
        conf = r.get("confidence", 0.5)
        if conf >= threshold and r.get("source") and r.get("target"):
            result.append(r)
    return result


def _get_effective_max_graph_chars(node_count: int) -> int:
    """Use larger context for large KBs so cross-component pairs are visible."""
    base = _get_max_graph_chars()
    if node_count > 500:
        return min(base * 2, 100_000)
    return base


def _build_graph_text(graph: OntologyGraph, node_count: int = 0) -> str:
    """Export graph to JSON string, truncated to effective max chars for LLM context."""
    max_chars = _get_effective_max_graph_chars(node_count or graph.get_graph().number_of_nodes())
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
    threshold = _get_confidence_threshold()
    logger.info(
        "[RelationInferer] Starting | nodes=%d | edges=%d | workers=%d | confidence_threshold=%.2f",
        nodes, edges, workers, threshold,
    )

    graph_text = _build_graph_text(graph, nodes)
    instances = graph.get_instances()
    classes = graph.get_classes()

    # Build inference tasks: partition entities into batches for parallel inference
    if not instances and not classes:
        logger.debug("[RelationInferer] No instances or classes, skipping inference")
        return []

    # Create batches: focus on instances if present, else use classes
    entities = instances if instances else classes
    g = graph.get_graph()
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    node_to_component: dict[str, int] = {}
    for idx, comp in enumerate(components):
        for n in comp:
            node_to_component[n] = idx

    # Stratify batches by component: mix entities from different components so inference can suggest cross-component relations
    min_per_batch = max(1, 3)
    batch_size = max(min_per_batch, (len(entities) + workers - 1) // workers)
    batches = _stratify_batches_by_component(
        entities, node_to_component, batch_size, num_components=len(components)
    )

    if not batches:
        batches = [entities[:1]]

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

    # Merge and deduplicate: max-confidence wins; vote-count bonus for triplets in 3+ batches
    key_to_best: dict[tuple[str, str, str], dict] = {}
    key_to_count: dict[tuple[str, str, str], int] = {}
    for content in responses:
        for r in _parse_inferred_relations(content):
            key = (r.get("source", ""), r.get("relation", ""), r.get("target", ""))
            if not key[0] or not key[2]:
                continue
            key_to_count[key] = key_to_count.get(key, 0) + 1
            conf = float(r.get("confidence", 0.5))
            if key not in key_to_best or conf > float(key_to_best[key].get("confidence", 0)):
                key_to_best[key] = dict(r)

    result = []
    for key, r in key_to_best.items():
        count = key_to_count.get(key, 1)
        conf = float(r.get("confidence", 0.5))
        if count >= 3:
            conf = min(1.0, conf + 0.1)
            r["confidence"] = conf
            r["vote_count"] = count
        r["provenance"] = {"origin": "inference_llm", "rule": "batch_inference", "confidence": conf}
        result.append(r)

    logger.info(
        "[RelationInferer] Complete | batches=%d | inferred_relations=%d",
        len(batches), len(result),
    )
    return result


def infer_cross_component_relations(
    graph: OntologyGraph,
    max_pairs: int = CROSS_COMPONENT_MAX_PAIRS,
) -> list[dict]:
    """Infer relations between entities in different connected components.

    Picks one representative per non-largest component and pairs them with
    a representative from the largest component; asks LLM to suggest relations.
    Limits to max_pairs to avoid token overflow.

    Returns:
        List of relation dicts (source, relation, target, confidence).
    """
    g = graph.get_graph()
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        logger.debug("[RelationInferer] Cross-component: 0 or 1 component, skipping")
        return []

    largest = max(components, key=len)
    others = [c for c in components if c != largest]
    # Representative per component: highest degree node
    rep_largest = max(largest, key=lambda n: g.degree(n)) if largest else None
    if not rep_largest:
        return []

    pairs: list[tuple[str, str]] = []
    for c in others[:max_pairs]:
        rep = max(c, key=lambda n: g.degree(n))
        pairs.append((rep, rep_largest))

    if not pairs:
        return []

    node_count = g.number_of_nodes()
    graph_summary = _build_graph_text(graph, node_count)
    pairs_text = "\n".join(f"- {src} | {tgt}" for src, tgt in pairs)
    user = CROSS_COMPONENT_INFERENCE_PROMPT.format(
        graph_summary=graph_summary,
        pairs_text=pairs_text,
    )
    settings = get_settings()
    try:
        raw = complete(
            system="You perform ontology reasoning. Output only valid JSON.",
            user=user,
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
    except Exception as e:
        logger.warning("[RelationInferer] Cross-component inference failed | error=%s", e)
        return []

    parsed = _parse_inferred_relations(raw or "")
    threshold = _get_confidence_threshold()
    # Apply same confidence filter as batch pass (cross-component previously bypassed it)
    result = []
    for r in parsed:
        if float(r.get("confidence", 0)) >= threshold:
            r["provenance"] = {"origin": "inference_llm", "rule": "cross_component", "confidence": r.get("confidence", 0.5)}
            result.append(r)
    logger.info(
        "[RelationInferer] Cross-component | pairs=%d | inferred_relations=%d",
        len(pairs), len(result),
    )
    return result
