"""Instance population booster: improve instance-to-class ratio (Fernández et al.)."""

from __future__ import annotations

import json
import logging
from typing import Any

from ontology_builder.llm.client import complete, complete_batch
from ontology_builder.llm.json_repair import repair_json
from ontology_builder.storage.graphdb import OntologyGraph
from core.config import get_settings

logger = logging.getLogger(__name__)

BOOST_INSTANCES_PROMPT = """\
Given the ontology class `{class_name}` (description: `{desc}`), identify up to 5 specific named individuals, examples, or instances of this class that are mentioned in the following text.
Return only individuals explicitly present in the text, not invented ones.
Reply as JSON: {{ "instances": [ {{ "name": "<string>", "description": "<brief>" }} ] }}
If none found, reply: {{ "instances": [] }}

Text:
{text_window}
"""


def boost_population(
    graph: OntologyGraph,
    source_text: str,
    config: Any,
) -> int:
    """Extract additional instances for under-populated classes. Returns new instances added."""
    if not getattr(config, "boost_population_if_sparse", True):
        return 0
    g = graph.get_graph()
    classes = [n for n, d in g.nodes(data=True) if d.get("kind") == "class"]
    instance_count = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "instance")
    if not classes or not source_text.strip():
        return 0
    ratio = instance_count / len(classes) if classes else 0
    if ratio >= 0.5:
        return 0

    # Top 10 most connected classes; prefer those with zero instances
    class_to_degree = {}
    class_to_instances = {}
    for n in classes:
        class_to_degree[n] = g.degree(n)
        class_to_instances[n] = sum(1 for _, v, d in g.in_edges(n, data=True) if d.get("relation") == "type")
    zero_instance_classes = [c for c in classes if class_to_instances.get(c, 0) == 0]
    if zero_instance_classes:
        candidates = sorted(zero_instance_classes, key=lambda c: class_to_degree.get(c, 0), reverse=True)[:10]
    else:
        candidates = sorted(classes, key=lambda c: class_to_degree.get(c, 0), reverse=True)[:10]

    window_size = 3000
    text_windows = [source_text[i : i + window_size] for i in range(0, min(len(source_text), 9000), window_size)]
    if not text_windows:
        text_windows = [source_text[:window_size]]

    tasks = []
    for cls in candidates:
        desc = g.nodes[cls].get("description", "")
        for win in text_windows[:2]:
            tasks.append((cls, desc, win))

    def user_fn(item):
        cls, desc, win = item
        return BOOST_INSTANCES_PROMPT.format(class_name=cls, desc=desc or cls, text_window=win[:2500])

    added = 0
    try:
        batch_size = 10
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            responses = complete_batch(
                items=batch,
                system_fn=lambda _: "You extract ontology instances from text. Reply only with valid JSON.",
                user_fn=user_fn,
                parallel=True,
                max_workers=get_settings().get_llm_parallel_workers(),
            )
            for (cls, _, _), raw in zip(batch, responses):
                try:
                    data = repair_json(raw or "{}")
                    inst_list = data.get("instances", [])
                    if not isinstance(inst_list, list):
                        continue
                    for inst in inst_list:
                        if not isinstance(inst, dict):
                            continue
                        name = (inst.get("name") or "").strip()
                        if not name or name in g:
                            continue
                        desc_inst = (inst.get("description") or "").strip()
                        graph.add_instance(
                            name, cls, description=desc_inst,
                            source_document="inferred",
                            provenance={"origin": "population_boost"},
                        )
                        added += 1
                except Exception as e:
                    logger.debug("[PopulationBooster] Parse failed: %s", e)
    except Exception as e:
        logger.warning("[PopulationBooster] LLM batch failed: %s", e)

    if added:
        logger.info("[PopulationBooster] Added %d instances", added)
    return added
