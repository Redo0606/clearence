"""LLM extraction of entities and relations from text chunks.

Expected return structure (legacy extraction):
{
  "entities": [
    {"name": "string", "type": "string", "description": "string"}
  ],
  "relations": [
    {"source": "string", "relation": "string", "target": "string", "confidence": 0}
  ]
}
"""

import json
import logging

from app.config import get_settings
from ontology_builder.llm.json_repair import repair_json
from ontology_builder.llm.lmstudio_client import call_llm
from ontology_builder.llm.prompts import (
    EXTRACT_CLASSES_SYSTEM,
    EXTRACT_CLASSES_USER,
    EXTRACT_INSTANCES_SYSTEM,
    EXTRACT_INSTANCES_USER,
    EXTRACT_RELATIONS_SYSTEM,
    EXTRACT_RELATIONS_USER,
    ONTOLOGY_EXTRACTION_PROMPT,
)
from ontology_builder.constants import CHARS_PER_TOKEN
from ontology_builder.ontology.schema import (
    Axiom,
    AxiomType,
    DataProperty,
    ObjectProperty,
    OntologyClass,
    OntologyExtraction,
    OntologyInstance,
)

logger = logging.getLogger(__name__)

LEGACY_EXTRACTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "legacy_ontology_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["name", "type", "description"],
                        "additionalProperties": False,
                    },
                },
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "relation": {"type": "string"},
                            "target": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["source", "relation", "target", "confidence"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["entities", "relations"],
            "additionalProperties": False,
        },
    },
}


def _is_structured_output_error(error: Exception) -> bool:
    """Return True when error likely indicates unsupported/invalid schema mode."""
    msg = str(error).lower()
    indicators = (
        "invalid json schema",
        "unrecognized schema",
        "structured output",
        "response_format",
        "json_schema",
        "unsupported",
    )
    return any(token in msg for token in indicators)


def _strip_fences(text: str) -> str:
    """Remove optional markdown code fences from LLM output."""
    cleaned = (text or "").strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _estimate_tokens(text: str) -> int:
    """Rough token count (1 token ≈ 4 chars). Good enough for budget guards."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _truncate_for_context(text: str, max_chars: int) -> str:
    """Truncate text to fit LLM context. Returns original if max_chars <= 0."""
    if max_chars <= 0 or not text:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...truncated for context...]"


def _parse_classes(raw: list, prov: dict) -> list[OntologyClass]:
    """Parse raw class dicts into OntologyClass list."""
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = c.get("name") or ""
        if not name:
            continue
        syn = c.get("synonyms", [])
        if isinstance(syn, list):
            syn = [str(s).strip() for s in syn if s]
        else:
            syn = []
        out.append(
            OntologyClass(
                name=name,
                parent=c.get("parent") or None,
                description=c.get("description") or "",
                synonyms=syn,
                **prov,
            )
        )
    return out


def _parse_instances(raw: list, prov: dict) -> list[OntologyInstance]:
    """Parse raw instance dicts into OntologyInstance list."""
    out = []
    for i in raw:
        if not isinstance(i, dict):
            continue
        name = i.get("name") or ""
        if not name:
            continue
        out.append(
            OntologyInstance(
                name=name,
                class_name=i.get("class_name") or "",
                description=i.get("description") or "",
                **prov,
            )
        )
    return out


def _parse_object_properties(data: dict, prov: dict) -> list[ObjectProperty]:
    """Parse object_properties from stage 3 data into ObjectProperty list."""
    out = []
    for op in data.get("object_properties", []) or []:
        if not isinstance(op, dict):
            continue
        source = op.get("source") or ""
        target = op.get("target") or ""
        if not source or not target:
            continue
        out.append(
            ObjectProperty(
                source=source,
                relation=op.get("relation") or "related_to",
                target=target,
                domain=op.get("domain"),
                range=op.get("range"),
                symmetric=bool(op.get("symmetric", False)),
                transitive=bool(op.get("transitive", False)),
                confidence=float(op.get("confidence", 1.0) or 1.0),
                **prov,
            )
        )
    return out


def _parse_data_properties(data: dict, prov: dict) -> list[DataProperty]:
    """Parse data_properties from stage 3 data into DataProperty list."""
    out = []
    for dp in data.get("data_properties", []) or []:
        if not isinstance(dp, dict):
            continue
        entity = dp.get("entity") or ""
        attribute = dp.get("attribute") or ""
        if not entity or not attribute:
            continue
        out.append(
            DataProperty(
                entity=entity,
                attribute=attribute,
                value=dp.get("value") or "",
                datatype=dp.get("datatype") or "string",
                **prov,
            )
        )
    return out


def _parse_axioms(data: dict, prov: dict) -> list[Axiom]:
    """Parse axioms from stage 3 data into Axiom list."""
    out = []
    for ax in data.get("axioms", []) or []:
        if not isinstance(ax, dict):
            continue
        try:
            axiom_type = AxiomType(ax.get("axiom_type", "subclass"))
            entities = ax.get("entities") or [""]
            if not entities:
                entities = [""]
            out.append(
                Axiom(
                    axiom_type=axiom_type,
                    entities=entities,
                    description=ax.get("description", ""),
                    **prov,
                )
            )
        except (ValueError, TypeError):
            continue
    return out


def _truncate_json_list(items: list, max_chars: int) -> tuple[list, str]:
    """Return (kept_items, json_str) truncated to max_chars. Keeps as many items as fit."""
    if not items:
        return [], "[]"
    kept: list = []
    for item in items:
        trial = json.dumps(kept + [item])
        if len(trial) <= max_chars:
            kept.append(item)
        else:
            break
    return kept, json.dumps(kept) if kept else "[]"


def _fit_chunk_to_budget(chunk: str, system: str, prompt_template: str, token_budget: int, **fmt_kwargs: str) -> str:
    """Shrink *chunk* so the assembled prompt fits within *token_budget*.

    Builds the full user message via ``prompt_template.format(chunk=chunk, **fmt_kwargs)``
    and estimates total tokens. If over budget, the chunk is progressively trimmed.
    """
    if token_budget <= 0:
        return chunk
    user_msg = prompt_template.format(chunk=chunk, **fmt_kwargs)
    total = _estimate_tokens(system) + _estimate_tokens(user_msg)
    if total <= token_budget:
        return chunk
    # Overshoot: (total - budget) tokens * CHARS_PER_TOKEN + 100 safety margin
    overshoot_chars = (total - token_budget) * CHARS_PER_TOKEN + 100
    new_len = max(200, len(chunk) - overshoot_chars)
    trimmed = chunk[:new_len] + "\n[...truncated for context...]"
    logger.debug("[Extractor] Trimmed chunk %d -> %d chars to fit token budget %d", len(chunk), new_len, token_budget)
    return trimmed


def extract_ontology(chunk: str) -> dict:
    """Call LLM to extract entities and relations from a text chunk.

    Args:
        chunk: Text chunk to analyze.

    Returns:
        Dict with "entities" and "relations" lists. Expected structure:
        - entities: [{"name": str, "type": str, "description": str}]
        - relations: [{"source": str, "relation": str, "target": str, "confidence": float}]
        Empty lists on LLM/parse error.
    """
    settings = get_settings()
    max_chars = getattr(settings, "llm_max_chunk_chars", 0)
    chunk_for_llm = _truncate_for_context(chunk, max_chars) if max_chars > 0 else chunk
    if chunk_for_llm != chunk:
        logger.debug("[Extractor] Truncated chunk %d -> %d chars for context", len(chunk), len(chunk_for_llm))

    logger.debug("[Extractor] Calling LLM | chunk_len=%d", len(chunk_for_llm))
    settings = get_settings()
    try:
        response = call_llm(
            system="You extract ontology structures. Output only valid JSON.",
            user=ONTOLOGY_EXTRACTION_PROMPT + chunk_for_llm,
            response_format=LEGACY_EXTRACTION_RESPONSE_FORMAT,
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
    except Exception as e:
        # Fallback: some models don't support json_schema; retry in plain text and parse JSON
        if _is_structured_output_error(e):
            logger.warning(
                "[Extractor] Structured output failed; retrying once in text mode | error=%s",
                e,
            )
            try:
                response = call_llm(
                    system="You extract ontology structures. Output only valid JSON.",
                    user=ONTOLOGY_EXTRACTION_PROMPT + chunk_for_llm,
                    force_text_mode=True,
                    temperature=getattr(settings, "llm_temperature", 0.1),
                )
            except Exception as fallback_err:
                logger.warning("[Extractor] LLM text fallback failed | error=%s", fallback_err)
                return {"entities": [], "relations": []}
        else:
            logger.warning("[Extractor] LLM call failed | error=%s", e)
            return {"entities": [], "relations": []}

    try:
        data = repair_json(response or "")
    except json.JSONDecodeError as e:
        logger.warning("[Extractor] Invalid JSON from LLM | error=%s | content_preview=%r", e, (response or "")[:200])
        return {"entities": [], "relations": []}

    if not isinstance(data, dict):
        return {"entities": [], "relations": []}

    entities = data.get("entities", [])
    relations = data.get("relations", [])
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []
    logger.debug("[Extractor] Parsed | entities=%d | relations=%d", len(entities), len(relations))
    return {"entities": entities, "relations": relations}


def extract_ontology_sequential(chunk: str, source_document: str = "") -> OntologyExtraction:
    """3-stage sequential extraction (Bakker Approach B): classes → instances → relations.

    Args:
        chunk: Text chunk to analyze.
        source_document: Path or identifier of the source document for provenance.

    Returns:
        OntologyExtraction with classes, instances, object_properties, data_properties, axioms.
    """
    prov = {"source_document": source_document, "source_chunk": chunk}

    settings = get_settings()
    max_chars = getattr(settings, "llm_max_chunk_chars", 0)
    token_budget = getattr(settings, "llm_max_prompt_tokens", 3000)
    chunk_for_llm = _truncate_for_context(chunk, max_chars) if max_chars > 0 else chunk
    if chunk_for_llm != chunk:
        logger.debug("[Extractor] Truncated chunk %d -> %d chars for context", len(chunk), len(chunk_for_llm))

    classes_raw: list[dict] | list = []
    try:
        # Stage 1: Extract classes
        s1_chunk = _fit_chunk_to_budget(
            chunk_for_llm, EXTRACT_CLASSES_SYSTEM, EXTRACT_CLASSES_USER,
            token_budget,
        )
        resp1 = call_llm(
            system=EXTRACT_CLASSES_SYSTEM,
            user=EXTRACT_CLASSES_USER.format(chunk=s1_chunk),
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
        data1 = repair_json(resp1 or "")
        # LLM may return {"classes": [...]} or bare list [...]
        if isinstance(data1, list):
            classes_raw = data1
        else:
            classes_raw = data1.get("classes", [])
        if not isinstance(classes_raw, list):
            classes_raw = []
    except Exception as e:
        logger.warning("[Extractor] Stage 1 (classes) failed | error=%s", e)
        classes_raw = []

    classes_list = [c for c in classes_raw if isinstance(c, dict)]
    kept_classes, classes_json = _truncate_json_list(classes_list, get_settings().llm_max_classes_json_chars)
    if len(kept_classes) < len(classes_list):
        logger.debug("[Extractor] Truncated classes %d -> %d for context", len(classes_list), len(kept_classes))

    try:
        # Stage 2: Extract instances given classes
        s2_chunk = _fit_chunk_to_budget(
            chunk_for_llm, EXTRACT_INSTANCES_SYSTEM, EXTRACT_INSTANCES_USER,
            token_budget, classes_json=classes_json,
        )
        resp2 = call_llm(
            system=EXTRACT_INSTANCES_SYSTEM,
            user=EXTRACT_INSTANCES_USER.format(classes_json=classes_json, chunk=s2_chunk),
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
        data2 = repair_json(resp2 or "")
        # LLM may return {"instances": [...]} or bare list [...]
        if isinstance(data2, list):
            instances_raw = data2
        else:
            instances_raw = data2.get("instances", [])
        if not isinstance(instances_raw, list):
            instances_raw = []
    except Exception as e:
        logger.warning("[Extractor] Stage 2 (instances) failed | error=%s", e)
        instances_raw = []

    instances_list = [i for i in instances_raw if isinstance(i, dict)]
    kept_instances, instances_json = _truncate_json_list(
        instances_list, get_settings().llm_max_instances_json_chars
    )
    if len(kept_instances) < len(instances_list):
        logger.debug("[Extractor] Truncated instances %d -> %d for context", len(instances_list), len(kept_instances))

    try:
        # Stage 3: Extract relations, data properties, axioms
        s3_chunk = _fit_chunk_to_budget(
            chunk_for_llm, EXTRACT_RELATIONS_SYSTEM, EXTRACT_RELATIONS_USER,
            token_budget, classes_json=classes_json, instances_json=instances_json,
        )
        resp3 = call_llm(
            system=EXTRACT_RELATIONS_SYSTEM,
            user=EXTRACT_RELATIONS_USER.format(
                classes_json=classes_json,
                instances_json=instances_json,
                chunk=s3_chunk,
            ),
            temperature=getattr(settings, "llm_temperature", 0.1),
        )
        data3 = repair_json(resp3 or "")
        if not isinstance(data3, dict):
            data3 = {}
    except Exception as e:
        logger.warning("[Extractor] Stage 3 (relations) failed | error=%s", e)
        data3 = {}

    return OntologyExtraction(
        classes=_parse_classes(classes_raw, prov),
        instances=_parse_instances(instances_raw, prov),
        object_properties=_parse_object_properties(data3, prov),
        data_properties=_parse_data_properties(data3, prov),
        axioms=_parse_axioms(data3, prov),
    )
