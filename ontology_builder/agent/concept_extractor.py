"""Extract key entities and concepts from user queries for reasoning graph initialization."""

from __future__ import annotations

import json
import logging
import re

from ontology_builder.llm.client import complete
from ontology_builder.llm.json_repair import repair_json

logger = logging.getLogger(__name__)

CONCEPT_EXTRACT_SYSTEM = """\
You extract key domain entities and concepts from user questions for ontology-based reasoning.

Your task: Given a user question, identify the main entities (proper nouns, domain terms), 
concepts (abstract ideas), and relation types that the question is about.

Rules:
- Extract 2–8 concepts. Prefer specific over generic (e.g. "Ezreal" over just "champion").
- Include both explicit mentions and implied concepts (e.g. "build" implies "item", "stat").
- Normalize to canonical form: lowercase, no extra punctuation.
- Return ONLY valid JSON with a "concepts" key containing a list of strings.

Example: "What should I build on Ezreal?" -> {"concepts": ["ezreal", "build", "champion", "item", "damage"]}
Example: "What counters Yasuo?" -> {"concepts": ["yasuo", "counter", "champion", "matchup"]}
"""


def extract_concepts(query: str) -> list[str]:
    """Extract key concepts from a user query via LLM.

    Args:
        query: Raw user question.

    Returns:
        List of normalized concept strings (e.g. ["ezreal", "build", "champion", "item"]).
    """
    if not query or not query.strip():
        return []

    user_prompt = f"""Extract key concepts from this question:\n\n{query.strip()}\n\nReply with JSON only: {{"concepts": [...]}}"""

    try:
        response = complete(
            system=CONCEPT_EXTRACT_SYSTEM,
            user=user_prompt,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning("[ConceptExtractor] LLM failed, using fallback: %s", e)
        return _fallback_extract(query)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(repair_json(response))
        except (json.JSONDecodeError, TypeError):
            return _fallback_extract(query)

    concepts = parsed.get("concepts", [])
    if not isinstance(concepts, list):
        concepts = [c for c in (concepts,) if isinstance(c, str)]

    result = []
    seen: set[str] = set()
    for c in concepts:
        if isinstance(c, str) and c.strip():
            norm = c.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                result.append(norm)

    if not result:
        return _fallback_extract(query)

    logger.debug("[ConceptExtractor] Extracted %d concepts: %s", len(result), result)
    return result


def _fallback_extract(query: str) -> list[str]:
    """Rule-based fallback when LLM is unavailable or fails."""
    # Remove common stopwords and punctuation, tokenize
    stop = {"what", "how", "why", "when", "where", "which", "who", "is", "are", "the", "a", "an", "on", "in", "to", "for", "of", "with", "should", "does", "do", "can", "?"}
    tokens = re.findall(r"\b[a-zA-Z0-9]+\b", query.lower())
    concepts = [t for t in tokens if t not in stop and len(t) > 1]
    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for t in concepts:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result[:10]  # Cap at 10
