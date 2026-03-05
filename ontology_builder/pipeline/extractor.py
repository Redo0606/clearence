"""LLM extraction of entities and relations from text chunks. Returns dict with entities and relations."""

import json
import logging
import re

from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.llm.prompts import ONTOLOGY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def extract_ontology(chunk: str) -> dict:
    """Call LLM to extract entities and relations from a text chunk.

    Args:
        chunk: Text chunk to analyze.

    Returns:
        Dict with "entities" and "relations" lists. Empty lists on LLM/parse error.
    """
    logger.debug("[Extractor] Calling LLM | chunk_len=%d", len(chunk))
    try:
        response = call_llm(
            system="You extract ontology structures. Output only valid JSON.",
            user=ONTOLOGY_EXTRACTION_PROMPT + chunk,
        )
    except Exception as e:
        logger.warning("[Extractor] LLM call failed | error=%s", e)
        return {"entities": [], "relations": []}

    content = (response or "").strip()
    # Strip markdown code fence if present
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("[Extractor] Invalid JSON from LLM | error=%s | content_preview=%r", e, content[:200])
        return {"entities": [], "relations": []}

    entities = data.get("entities", [])
    relations = data.get("relations", [])
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []
    logger.debug("[Extractor] Parsed | entities=%d | relations=%d", len(entities), len(relations))
    return {"entities": entities, "relations": relations}
