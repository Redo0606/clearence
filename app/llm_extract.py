"""LLM ontology schema extraction from text. Uses OpenAI or LM Studio (OpenAI-compatible API)."""

import json
import logging

from app.config import get_settings
from app.schemas import OntologySchema
from ontology_builder.llm.client import complete

logger = logging.getLogger(__name__)

# Truncate PDF text to stay within typical context limits (e.g. ~100k chars)
MAX_TEXT_CHARS = 100_000

SYSTEM_PROMPT = """You are an expert at building ontologies from domain documentation.
Your task is to analyze the provided text and extract a structured ontology schema.
Output only valid JSON matching this structure (no markdown, no code fences):
- namespace_prefix: short identifier (e.g. "field")
- namespace_uri: full URI ending with # (e.g. "http://example.org/field#")
- classes: list of { "name": "ClassName", "parent": null or "ParentClass" }
- object_properties: list of { "name": "propertyName", "domain": "ClassA", "range": "ClassB" }
- datatype_properties: list of { "name": "propertyName", "domain": "ClassA", "range": "string" | "int" | "float" | "date" | "boolean" }
Identify all important domain concepts as classes, relationships between concepts as object_properties, and attributes as datatype_properties. Use PascalCase for class names and camelCase for property names."""


def extract_ontology_schema(text: str) -> OntologySchema:
    """
    Call the configured LLM (OpenAI or LM Studio) to extract an ontology schema from text.
    Uses OPENAI_BASE_URL (default: LM Studio at http://localhost:1234/v1) and OPENAI_API_KEY.
    """
    settings = get_settings()
    logger.info("[LLM] Extracting ontology schema | text_length=%d | model=%s | base_url=%s",
                len(text), settings.ontology_llm_model, settings.openai_base_url)
    if not settings.get_llm_api_key() and "localhost" not in settings.openai_base_url and "127.0.0.1" not in settings.openai_base_url:
        raise ValueError("OPENAI_API_KEY is required when not using a local LLM (e.g. LM Studio)")

    if len(text) > MAX_TEXT_CHARS:
        logger.debug("[LLM] Truncating text from %d to %d chars", len(text), MAX_TEXT_CHARS)
        text = text[:MAX_TEXT_CHARS] + "\n\n[Text truncated for context limit.]"

    user_content = f"Extract an ontology schema from the following documentation:\n\n{text}"

    try:
        content = complete(system=SYSTEM_PROMPT, user=user_content, temperature=0.1)
    except RuntimeError as e:
        logger.exception("LLM request failed")
        raise RuntimeError(f"LLM request failed: {e}") from e

    content = content.strip()
    # Strip markdown code fence if present (some models return ```json ... ```)
    # to avoid JSONDecodeError on the raw string
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        data = json.loads(content)
        logger.debug("[LLM] JSON parsed successfully | keys=%s", list(data.keys()) if isinstance(data, dict) else "N/A")
    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s", content[:500])
        raise RuntimeError(f"LLM returned invalid JSON: {e}") from e

    schema = OntologySchema.model_validate(data)
    logger.info("[LLM] Schema validated | classes=%d | object_properties=%d | datatype_properties=%d",
                len(schema.classes), len(schema.object_properties), len(schema.datatype_properties))
    return schema
