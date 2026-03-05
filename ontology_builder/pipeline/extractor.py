"""LLM extraction of entities and relations from text chunks. Returns dict with entities and relations."""

import json
import logging
import re

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


def _strip_fences(content: str) -> str:
    """Strip markdown code fence from LLM response."""
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    return content


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

    content = _strip_fences(response or "")

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


def extract_ontology_sequential(chunk: str, source_document: str = "") -> OntologyExtraction:
    """3-stage sequential extraction (Bakker Approach B): classes → instances → relations.

    Args:
        chunk: Text chunk to analyze.
        source_document: Path or identifier of the source document for provenance.

    Returns:
        OntologyExtraction with classes, instances, object_properties, data_properties, axioms.
    """
    prov = {"source_document": source_document, "source_chunk": chunk}

    try:
        # Stage 1: Extract classes
        resp1 = call_llm(
            system=EXTRACT_CLASSES_SYSTEM,
            user=EXTRACT_CLASSES_USER.format(chunk=chunk),
        )
        data1 = json.loads(_strip_fences(resp1 or ""))
        classes_raw = data1.get("classes", [])
        if not isinstance(classes_raw, list):
            classes_raw = []
    except Exception as e:
        logger.warning("[Extractor] Stage 1 (classes) failed | error=%s", e)
        return OntologyExtraction()

    classes_json = json.dumps([c for c in classes_raw if isinstance(c, dict)])

    try:
        # Stage 2: Extract instances given classes
        resp2 = call_llm(
            system=EXTRACT_INSTANCES_SYSTEM,
            user=EXTRACT_INSTANCES_USER.format(classes_json=classes_json, chunk=chunk),
        )
        data2 = json.loads(_strip_fences(resp2 or ""))
        instances_raw = data2.get("instances", [])
        if not isinstance(instances_raw, list):
            instances_raw = []
    except Exception as e:
        logger.warning("[Extractor] Stage 2 (instances) failed | error=%s", e)
        instances_raw = []

    instances_json = json.dumps([i for i in instances_raw if isinstance(i, dict)])

    try:
        # Stage 3: Extract relations, data properties, axioms
        resp3 = call_llm(
            system=EXTRACT_RELATIONS_SYSTEM,
            user=EXTRACT_RELATIONS_USER.format(
                classes_json=classes_json,
                instances_json=instances_json,
                chunk=chunk,
            ),
        )
        data3 = json.loads(_strip_fences(resp3 or ""))
    except Exception as e:
        logger.warning("[Extractor] Stage 3 (relations) failed | error=%s", e)
        data3 = {}

    def make_classes():
        out = []
        for c in classes_raw:
            if not isinstance(c, dict):
                continue
            out.append(OntologyClass(
                name=c.get("name", ""),
                parent=c.get("parent"),
                description=c.get("description", ""),
                **prov,
            ))
        return out

    def make_instances():
        out = []
        for i in instances_raw:
            if not isinstance(i, dict):
                continue
            out.append(OntologyInstance(
                name=i.get("name", ""),
                class_name=i.get("class_name", ""),
                description=i.get("description", ""),
                **prov,
            ))
        return out

    def make_object_properties():
        out = []
        for op in data3.get("object_properties", []) or []:
            if not isinstance(op, dict):
                continue
            out.append(ObjectProperty(
                source=op.get("source", ""),
                relation=op.get("relation", "related_to"),
                target=op.get("target", ""),
                domain=op.get("domain"),
                range=op.get("range"),
                symmetric=bool(op.get("symmetric", False)),
                transitive=bool(op.get("transitive", False)),
                confidence=float(op.get("confidence", 1.0)),
                **prov,
            ))
        return out

    def make_data_properties():
        out = []
        for dp in data3.get("data_properties", []) or []:
            if not isinstance(dp, dict):
                continue
            out.append(DataProperty(
                entity=dp.get("entity", ""),
                attribute=dp.get("attribute", ""),
                value=dp.get("value", ""),
                datatype=dp.get("datatype", "string"),
                **prov,
            ))
        return out

    def make_axioms():
        out = []
        for ax in data3.get("axioms", []) or []:
            if not isinstance(ax, dict):
                continue
            try:
                axiom_type = AxiomType(ax.get("axiom_type", "subclass"))
                entities = ax.get("entities") or [""]
                if not entities:
                    entities = [""]
                out.append(Axiom(
                    axiom_type=axiom_type,
                    entities=entities,
                    description=ax.get("description", ""),
                    **prov,
                ))
            except (ValueError, TypeError):
                continue
        return out

    return OntologyExtraction(
        classes=make_classes(),
        instances=make_instances(),
        object_properties=make_object_properties(),
        data_properties=make_data_properties(),
        axioms=make_axioms(),
    )
