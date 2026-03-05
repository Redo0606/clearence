"""PDF-to-OWL API routes. POST /ontology/from-pdf returns OWL/Turtle/JSON-LD."""

import logging
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.llm_extract import extract_ontology_schema
from app.ontology import build_ontology, serialize_ontology
from app.pdf import PDFExtractionError, extract_text_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontology", tags=["ontology"])


@router.post("/from-pdf")
async def ontology_from_pdf(
    file: UploadFile = File(..., description="PDF file (field documentation)"),
    output_format: str = Query("owl", description="Output format: owl, turtle, json-ld"),
    response_type: str = Query("file", description="Response: file (download) or json"),
):
    """Upload PDF, extract ontology schema via LLM, return OWL/Turtle/JSON-LD.

    Pipeline: PDF text extraction → LLM schema extraction → rdflib graph → serialize.
    Uses LM Studio (localhost:1234) or OpenAI per OPENAI_BASE_URL.
    """
    settings = get_settings()
    if output_format not in ("owl", "turtle", "json-ld"):
        raise HTTPException(400, "output_format must be owl, turtle, or json-ld")
    if response_type not in ("file", "json"):
        raise HTTPException(400, "response_type must be file or json")

    logger.info("[PDF→OWL] Request received | file=%s | output_format=%s | response_type=%s",
                file.filename, output_format, response_type)

    content_type = file.content_type or ""
    if "pdf" not in content_type and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")

    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    content = await file.read()
    logger.debug("[PDF→OWL] File read | size=%d bytes | max_allowed=%d bytes", len(content), max_bytes)
    if len(content) > max_bytes:
        raise HTTPException(400, f"File too large (max {settings.upload_max_size_mb} MB)")

    logger.info("[PDF→OWL] Step 1/4: Extracting text from PDF")
    try:
        text = extract_text_from_pdf(content)
        logger.info("[PDF→OWL] Text extracted | length=%d chars", len(text))
    except PDFExtractionError as e:
        raise HTTPException(400, str(e)) from e

    logger.info("[PDF→OWL] Step 2/4: Calling LLM to extract ontology schema")
    try:
        schema = extract_ontology_schema(text)
        logger.info("[PDF→OWL] Schema extracted | classes=%d | object_props=%d | datatype_props=%d",
                    len(schema.classes), len(schema.object_properties), len(schema.datatype_properties))
    except ValueError as e:
        raise HTTPException(503, str(e)) from e
    except RuntimeError as e:
        logger.exception("LLM extraction failed")
        raise HTTPException(500, f"Ontology extraction failed: {e}") from e

    logger.info("[PDF→OWL] Step 3/4: Building rdflib graph from schema")
    graph = build_ontology(schema)
    logger.debug("[PDF→OWL] Graph built | triples=%d", len(graph))

    logger.info("[PDF→OWL] Step 4/4: Serializing to %s", output_format)
    try:
        serialized = serialize_ontology(graph, output_format)
        logger.info("[PDF→OWL] Serialization complete | output_length=%d", len(serialized) if isinstance(serialized, str) else len(serialized))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if isinstance(serialized, bytes):
        serialized = serialized.decode("utf-8")

    if response_type == "json":
        return {
            "namespace": schema.namespace_uri,
            "format": output_format,
            "class_count": len(schema.classes),
            "object_property_count": len(schema.object_properties),
            "datatype_property_count": len(schema.datatype_properties),
            "content": serialized,
        }

    # File response
    media_types = {"owl": "application/xml", "turtle": "text/turtle", "json-ld": "application/ld+json"}
    ext = "owl" if output_format == "owl" else output_format
    filename = f"ontology.{ext}"
    return Response(
        content=serialized.encode("utf-8"),
        media_type=media_types.get(output_format, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
