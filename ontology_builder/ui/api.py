"""Living ontology API routes: build_ontology, graph, reasoning/apply, qa/ask.

All endpoints return typed Pydantic response models with full pipeline metadata.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from ontology_builder.pipeline.run_pipeline import process_document
from ontology_builder.qa.answer import answer_question
from ontology_builder.qa.graph_index import (
    build_index as build_qa_index,
    retrieve_hyperedges,
    retrieve_with_context,
)
from ontology_builder.reasoning.engine import run_inference as apply_reasoning
from ontology_builder.storage.graph_store import (
    clear as clear_graph_store,
    get_current_kb_id,
    get_export,
    get_graph,
    get_ontology_graphs_dir,
    get_subject,
    list_knowledge_bases,
    load_from_path,
    save_to_path_with_metadata,
    set_current_kb_id,
    set_graph,
)
from ontology_builder.ui.graph_viewer import generate_visjs_html, visualize

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCUMENTS_RAW = _REPO_ROOT / "documents" / "raw"
_ONTOLOGY_GRAPHS = get_ontology_graphs_dir()
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PipelineReportResponse(BaseModel):
    document_path: str = ""
    total_chunks: int = 0
    totals: dict[str, int] = Field(default_factory=dict)
    extraction_totals: dict[str, int] = Field(default_factory=dict)
    llm_inferred_relations: int = 0
    reasoning: dict[str, Any] = Field(default_factory=dict)
    elapsed_seconds: float = 0.0
    extraction_mode: str = "sequential"
    chunk_stats: list[dict[str, Any]] = Field(default_factory=list)
    ontology_name: str = ""


class BuildOntologyResponse(BaseModel):
    graph: dict[str, Any] = Field(default_factory=dict)
    pipeline_report: PipelineReportResponse = Field(default_factory=PipelineReportResponse)
    kb_id: str | None = None


class QASourceResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontological_context: str = ""
    num_facts_used: int = 0


class GraphExportResponse(BaseModel):
    graph: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, int] = Field(default_factory=dict)


class ReasoningResponse(BaseModel):
    inferred_edges: int = 0
    iterations: int = 0
    consistency_violations: list[str] = Field(default_factory=list)
    inference_trace: list[dict[str, str]] = Field(default_factory=list)
    graph: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseItem(BaseModel):
    id: str
    name: str
    created_at: float
    stats: dict[str, int] = Field(default_factory=dict)


class KnowledgeBasesResponse(BaseModel):
    items: list[KnowledgeBaseItem] = Field(default_factory=list)
    active_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class QAAskRequest(BaseModel):
    question: str


@router.post("/build_ontology", response_model=BuildOntologyResponse)
async def build_ontology(
    file: UploadFile = File(..., description="Document (PDF, DOCX, TXT, MD)"),
    title: str | None = Form(None, description="Ontology title (default: filename stem)"),
    description: str | None = Form(None, description="Ontology description"),
    run_inference: bool = Query(True, description="Run LLM relation inference after extraction"),
    sequential: bool = Query(True, description="Use 3-stage sequential extraction (Bakker B)"),
    run_reasoning: bool = Query(True, description="Run OWL 2 RL reasoning after extraction"),
):
    """Upload a document and run the theory-grounded ontology pipeline.

    Returns the graph and a full pipeline report with per-chunk stats.
    """
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported format. Use one of: {', '.join(_ALLOWED_SUFFIXES)}")

    logger.info("[BuildOntology] file=%s inference=%s sequential=%s reasoning=%s",
                file.filename, run_inference, sequential, run_reasoning)

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = _DOCUMENTS_RAW / unique_name

    try:
        content = await file.read()
        temp_path.write_bytes(content)
    except Exception as e:
        logger.exception("Failed to save upload")
        raise HTTPException(500, f"Failed to save file: {e}") from e

    try:
        graph, report = await asyncio.to_thread(
            process_document,
            str(temp_path),
            run_inference=run_inference,
            verbose=False,
            sequential=sequential,
            run_reasoning=run_reasoning,
        )
        set_graph(graph, document_subject=None)
        await asyncio.to_thread(build_qa_index, graph, False)

        kb_id = uuid.uuid4().hex
        name = (title or Path(file.filename).stem or f"ontology-{kb_id[:8]}").strip() or f"ontology-{kb_id[:8]}"
        saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        _ONTOLOGY_GRAPHS.mkdir(parents=True, exist_ok=True)
        save_to_path_with_metadata(saved_path, name=name, kb_id=kb_id, description=description or "")
        set_current_kb_id(kb_id)

        report_dict = report.to_dict()
        return BuildOntologyResponse(
            graph=graph.export(),
            kb_id=kb_id,
            pipeline_report=PipelineReportResponse(
                document_path=report_dict.get("document_path", ""),
                total_chunks=report_dict.get("total_chunks", 0),
                totals=report_dict.get("totals", {}),
                extraction_totals=report_dict.get("extraction_totals", {}),
                llm_inferred_relations=report_dict.get("llm_inferred_relations", 0),
                reasoning=report_dict.get("reasoning", {}),
                elapsed_seconds=report_dict.get("elapsed_seconds", 0.0),
                extraction_mode=report_dict.get("extraction_mode", ""),
                chunk_stats=report_dict.get("chunk_stats", []),
                ontology_name=name,
            ),
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("Pipeline failed")
        raise HTTPException(500, f"Pipeline failed: {e}") from e
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def list_kb():
    """List persisted knowledge bases."""
    items = list_knowledge_bases()
    kb_items = [
        KnowledgeBaseItem(
            id=it["id"],
            name=it["name"],
            created_at=it["created_at"],
            stats=it.get("stats", {}),
        )
        for it in items
    ]
    return KnowledgeBasesResponse(
        items=kb_items,
        active_id=get_current_kb_id(),
    )


@router.post("/knowledge-bases/{kb_id}/activate")
async def activate_kb(kb_id: str):
    """Load a knowledge base from disk and set it as active."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    try:
        graph = load_from_path(path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False)
        return {"status": "ok", "active_id": kb_id}
    except Exception as e:
        logger.exception("Failed to load knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to load knowledge base: {e}") from e


@router.delete("/knowledge-bases/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a persisted knowledge base."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    try:
        path.unlink(missing_ok=True)
        if meta_path.exists():
            meta_path.unlink()
        if get_current_kb_id() == kb_id:
            clear_graph_store()
            set_current_kb_id(None)
        return {"status": "ok", "deleted_id": kb_id}
    except OSError as e:
        logger.exception("Failed to delete knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to delete: {e}") from e


@router.post("/qa/ask", response_model=QASourceResponse)
async def qa_ask(
    req: QAAskRequest,
    retrieval_mode: str = Query("context", description="'context' (ontology-grounded), 'hyperedges', or 'snippets'"),
):
    """Answer a question using ontology-grounded RAG retrieval with attribution."""
    logger.info("[QA] question=%r mode=%s", req.question[:80], retrieval_mode)
    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "No ontology graph. Build one first via POST /build_ontology.")

    if retrieval_mode == "hyperedges":
        context_snippets = retrieve_hyperedges(req.question, k_nodes=10, max_hyperedges=5)
        source_refs = [f"he:{i}" for i in range(len(context_snippets))]
        onto_ctx = ""
    elif retrieval_mode == "context":
        result = retrieve_with_context(req.question, top_k=10)
        context_snippets = result.facts
        source_refs = result.source_refs
        onto_ctx = result.ontological_context
    else:
        result = retrieve_with_context(req.question, top_k=10)
        context_snippets = result.facts
        source_refs = result.source_refs
        onto_ctx = ""

    if not context_snippets:
        raise HTTPException(503, "QA index is empty. Rebuild the ontology.")

    try:
        qa_result = await asyncio.to_thread(
            answer_question,
            req.question,
            context_snippets,
            source_refs,
            onto_ctx,
        )
    except Exception as e:
        logger.exception("QA LLM failed")
        raise HTTPException(500, f"Answer generation failed: {e}") from e

    return QASourceResponse(
        answer=qa_result.answer,
        sources=context_snippets,
        source_refs=qa_result.sources,
        ontological_context=qa_result.ontological_context,
        num_facts_used=qa_result.num_facts_used,
    )


@router.get("/graph", response_model=GraphExportResponse)
async def get_current_graph():
    """Return the current graph export with class/instance/edge/axiom counts."""
    data = get_export()
    if data is None:
        raise HTTPException(404, "No ontology graph. Build one first via POST /build_ontology.")
    return GraphExportResponse(
        graph=data,
        stats=data.get("stats", {}),
    )


@router.post("/reasoning/apply", response_model=ReasoningResponse)
async def reasoning_apply():
    """Re-run OWL 2 RL reasoning on the stored graph. Returns inference trace."""
    graph = get_graph()
    if graph is None:
        raise HTTPException(404, "No ontology graph. Build one first via POST /build_ontology.")

    subject = get_subject()
    reasoning_result = await asyncio.to_thread(apply_reasoning, graph, subject)

    set_graph(graph, document_subject=subject)
    await asyncio.to_thread(build_qa_index, graph, False)

    return ReasoningResponse(
        inferred_edges=reasoning_result.inferred_edges,
        iterations=reasoning_result.iterations,
        consistency_violations=reasoning_result.consistency_violations,
        inference_trace=reasoning_result.inference_trace,
        graph=graph.export(),
    )


# ---------------------------------------------------------------------------
# Visualization endpoints
# ---------------------------------------------------------------------------

@router.get("/graph/image")
async def graph_image():
    """Render the current graph as a PNG image."""
    graph = get_graph()
    if graph is None:
        raise HTTPException(404, "No ontology graph. Build one first.")
    buf = await asyncio.to_thread(visualize, graph)
    if buf is None:
        raise HTTPException(404, "Graph is empty.")
    return StreamingResponse(buf, media_type="image/png")


@router.get("/graph/viewer", response_class=HTMLResponse)
async def graph_viewer():
    """Interactive vis.js graph viewer (standalone HTML page)."""
    graph = get_graph()
    if graph is None:
        raise HTTPException(404, "No ontology graph. Build one first.")
    html = generate_visjs_html(graph)
    return HTMLResponse(content=html)
