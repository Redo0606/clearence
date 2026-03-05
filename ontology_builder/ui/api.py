"""Living ontology API routes: build_ontology, graph, reasoning/apply, qa/ask."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ontology_builder.pipeline.run_pipeline import process_document
from ontology_builder.qa.answer import answer_question
from ontology_builder.qa.graph_index import build_index as build_qa_index, retrieve, retrieve_hyperedges
from ontology_builder.reasoning.engine import run_inference as apply_reasoning
from ontology_builder.storage.graph_store import get_export, get_graph, get_subject, set_graph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])

# Project root: ontology_builder/ui/api.py -> parent.parent = ontology_builder, parent.parent.parent = repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCUMENTS_RAW = _REPO_ROOT / "documents" / "raw"

# Allowed extensions for build_ontology
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


@router.post("/build_ontology")
async def build_ontology(
    file: UploadFile = File(..., description="Document (PDF, DOCX, TXT, MD)"),
    run_inference: bool = Query(True, description="Run relation inference after extraction"),
):
    """
    Upload a document, run the living-ontology pipeline (chunk, extract, canonicalize, graph, optional inference),
    and return the graph as node-link JSON. Uses the same LM Studio config as the rest of the app.
    """
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported format. Use one of: {', '.join(_ALLOWED_SUFFIXES)}")

    logger.info("[BuildOntology] Request received | file=%s | run_inference=%s", file.filename, run_inference)

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = _DOCUMENTS_RAW / unique_name

    try:
        content = await file.read()
        saved_path.write_bytes(content)
        logger.debug("[BuildOntology] File saved | path=%s | size=%d bytes", saved_path, len(content))
    except Exception as e:
        logger.exception("Failed to save upload")
        raise HTTPException(500, f"Failed to save file: {e}") from e

    try:
        logger.info("[BuildOntology] Step 1/4: Running document pipeline")
        graph = process_document(str(saved_path), run_inference=run_inference)
        logger.info("[BuildOntology] Step 2/4: Applying axiom-based reasoning")
        apply_reasoning(graph, subject=None)
        logger.info("[BuildOntology] Step 3/4: Storing graph and building QA index")
        set_graph(graph, document_subject=None)
        build_qa_index(graph)
        logger.info("[BuildOntology] Step 4/4: Complete | nodes=%d | edges=%d",
                    graph.get_graph().number_of_nodes(), graph.get_graph().number_of_edges())
        return graph.export()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("Pipeline failed")
        raise HTTPException(500, f"Pipeline failed: {e}") from e
    finally:
        if saved_path.exists():
            try:
                saved_path.unlink()
            except OSError:
                pass


class QAAskRequest(BaseModel):
    question: str


@router.post("/qa/ask")
async def qa_ask(
    req: QAAskRequest,
    retrieval_mode: str = Query("snippets", description="Retrieval mode: 'snippets' (dual retrieval) or 'hyperedges'"),
):
    """
    Answer a natural-language question using the current ontology graph (RAG).
    Build an ontology first via POST /build_ontology. Uses same LM Studio/OpenAI config.
    """
    logger.info("[QA] Request received | question=%r | retrieval_mode=%s", req.question[:80], retrieval_mode)
    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "No ontology graph available. Build one first via POST /build_ontology.")
    if retrieval_mode == "hyperedges":
        logger.debug("[QA] Retrieving via hyperedges")
        context_snippets = retrieve_hyperedges(req.question, k_nodes=10, max_hyperedges=5)
    else:
        logger.debug("[QA] Retrieving via dual (key+value) similarity")
        context_snippets = retrieve(req.question, top_k=10)
    logger.info("[QA] Retrieved %d context snippets", len(context_snippets))
    if not context_snippets:
        raise HTTPException(503, "QA index is empty. Rebuild the ontology.")
    try:
        logger.debug("[QA] Generating answer via LLM")
        answer = answer_question(req.question, context_snippets)
    except Exception as e:
        logger.exception("QA LLM failed")
        raise HTTPException(500, f"Answer generation failed: {e}") from e
    return {"answer": answer, "sources": context_snippets}


@router.get("/graph")
async def get_current_graph():
    """Return the current stored graph export (node-link JSON), or 404 if none."""
    data = get_export()
    if data is None:
        raise HTTPException(404, "No ontology graph available. Build one first via POST /build_ontology.")
    return data


@router.post("/reasoning/apply")
async def reasoning_apply():
    """
    Re-run reasoning (transitive/symmetric closure) on the stored graph.
    Returns updated graph export and number of edges added.
    """
    logger.info("[Reasoning] Re-running transitive/symmetric closure")
    graph = get_graph()
    if graph is None:
        raise HTTPException(404, "No ontology graph available. Build one first via POST /build_ontology.")
    subject = get_subject()
    added = apply_reasoning(graph, subject=subject)
    logger.info("[Reasoning] Complete | edges_added=%d", added)
    set_graph(graph, document_subject=subject)
    build_qa_index(graph)
    return {"edges_added": added, "graph": graph.export()}
