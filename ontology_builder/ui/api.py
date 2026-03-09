"""Living ontology API routes: build_ontology, graph, reasoning/apply, qa/ask.

All endpoints return typed Pydantic response models with full pipeline metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from queue import Queue
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from ontology_builder.evaluation.graph_health import compute_graph_health
from ontology_builder.pipeline.run_pipeline import PipelineCancelledError, process_document
from ontology_builder.qa.answer import answer_question, source_ref_to_label
from ontology_builder.qa.graph_index import (
    build_index as build_qa_index,
    clear_index as clear_qa_index,
    retrieve_hyperedges,
    retrieve_with_context,
)
from ontology_builder.reasoning.engine import run_inference as apply_reasoning
from ontology_builder.export.owl_exporter import export_ontology_to_rdf
from ontology_builder.storage.graph_store import (
    clear as clear_graph_store,
    clear_last_active_kb,
    get_current_kb_id,
    get_export,
    get_export_for_api,
    get_graph,
    get_ontology_graphs_dir,
    get_subject,
    list_knowledge_bases,
    load_from_path,
    save_to_path,
    save_to_path_with_metadata,
    set_current_kb_id,
    set_graph,
)
from core.config import get_settings
from ontology_builder.ui.graph_viewer import (
    _persist_vis_data,
    generate_visjs_html,
    render_vis_from_file,
    visualize,
)

logger = logging.getLogger(__name__)

# Models available for selection in the UI
_AVAILABLE_MODELS = ["gpt-4.1o-mini", "gpt-4o-mini", "phi-3-mini-4k-instruct", "gpt-4o", "gpt-4-turbo"]

router = APIRouter(tags=["ontology-builder"])

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCUMENTS_RAW = _REPO_ROOT / "documents" / "raw"
_ONTOLOGY_GRAPHS = get_ontology_graphs_dir()
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}

_active_pipelines: dict[str, threading.Event] = {}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PipelineReportResponse(BaseModel):
    """Pipeline execution report with extraction, reasoning, and quality stats (Plan 2)."""

    document_path: str = Field("", description="Path to source document")
    total_chunks: int = Field(0, description="Number of text chunks processed")
    totals: dict[str, int] = Field(default_factory=dict, description="Final graph counts")
    extraction_totals: dict[str, int] = Field(default_factory=dict, description="Counts before reasoning")
    llm_inferred_relations: int = Field(0, description="Relations inferred by LLM")
    reasoning: dict[str, Any] = Field(default_factory=dict, description="OWL 2 RL reasoning stats")
    elapsed_seconds: float = Field(0.0, description="Total pipeline duration")
    extraction_mode: str = Field("sequential", description="legacy, parallel, or sequential")
    chunk_stats: list[dict[str, Any]] = Field(default_factory=list, description="Per-chunk extraction stats")
    ontology_name: str = Field("", description="Display name of the ontology")
    quality: dict[str, Any] | None = Field(None, description="OntologyQualityReport: structural metrics, reliability grade, recommended actions")
    health: dict[str, Any] | None = Field(None, description="Graph health: badge, overall_score, structural/semantic/retrieval metrics")


class BuildOntologyResponse(BaseModel):
    """Response from build_ontology with graph and pipeline report."""

    graph: dict[str, Any] = Field(default_factory=dict, description="Node-link graph export")
    pipeline_report: PipelineReportResponse = Field(default_factory=PipelineReportResponse)
    kb_id: str | None = Field(None, description="ID of created knowledge base")


class QASourceResponse(BaseModel):
    """QA answer with fact-level attribution and explainable reasoning."""

    answer: str = Field(..., description="Generated natural language answer")
    reasoning: str = Field("", description="In-depth interpretation of the facts")
    sources: list[str] = Field(default_factory=list, description="Retrieved fact strings (raw facts)")
    source_refs: list[str] = Field(default_factory=list, description="Source reference IDs")
    source_labels: list[str] = Field(default_factory=list, description="Human-readable source labels")
    ontological_context: str = Field("", description="OntoRAG taxonomy context")
    num_facts_used: int = Field(0, description="Number of facts used in answer")
    kb_id: str | None = Field(None, description="Ontology that was queried")


class GraphExportResponse(BaseModel):
    """Graph export with node-link data and stats."""

    graph: dict[str, Any] = Field(default_factory=dict, description="Node-link JSON")
    stats: dict[str, int] = Field(default_factory=dict, description="Class/instance/edge counts")


class ReasoningResponse(BaseModel):
    """OWL 2 RL reasoning result with trace."""

    inferred_edges: int = Field(0, description="Number of edges inferred")
    iterations: int = Field(0, description="Fixpoint iterations")
    consistency_violations: list[str] = Field(default_factory=list, description="Disjointness violations")
    inference_trace: list[dict[str, str]] = Field(default_factory=list, description="Step-by-step trace")
    graph: dict[str, Any] = Field(default_factory=dict, description="Updated graph export")


class KnowledgeBaseItem(BaseModel):
    """Single knowledge base metadata."""

    id: str = Field(..., description="Unique KB ID")
    name: str = Field(..., description="Display name")
    description: str = Field("", description="Optional description")
    created_at: float = Field(..., description="Unix timestamp")
    stats: dict[str, int] = Field(default_factory=dict, description="Graph stats")
    documents: list[str] = Field(default_factory=list, description="Source document filenames")
    ontology_language: str = Field("en", description="ISO 639-1 language of the ontology (all node/edge text)")


class KnowledgeBasesResponse(BaseModel):
    """List of knowledge bases with active ID."""

    items: list[KnowledgeBaseItem] = Field(default_factory=list)
    active_id: str | None = Field(None, description="Currently active KB ID")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class QAAskRequest(BaseModel):
    question: str
    kb_id: str | None = Field(None, description="Ontology/knowledge base ID to query. If provided and different from active, activates it first.")
    answer_language: str | None = Field(None, description="ISO 639-1 code for answer language (e.g. en, fr). If omitted, answer in the same language as the question.")


class SettingsResponse(BaseModel):
    model: str = ""
    workers: int = 2
    chunk_size: int = 1200
    chunk_overlap: int = 200
    temperature: float = 0.1
    available_models: list[str] = Field(default_factory=list)


@router.get("/settings", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    """Return current LLM settings for the UI (model, workers, chunk params)."""
    s = get_settings()
    return SettingsResponse(
        model=s.ontology_llm_model,
        workers=s.get_llm_parallel_workers(),
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        temperature=s.llm_temperature,
        available_models=_AVAILABLE_MODELS,
    )


def _normalize_files(
    file: UploadFile | None = None,
    files: list[UploadFile] | None = None,
) -> list[UploadFile]:
    """Normalize single file or multiple files into a list."""
    if files:
        return [f for f in files if f.filename]
    if file and file.filename:
        return [file]
    return []


@router.post("/build_ontology", response_model=BuildOntologyResponse)
async def build_ontology(
    file: UploadFile | None = File(None, description="Single document (PDF, DOCX, TXT, MD)"),
    files: list[UploadFile] | None = File(None, description="Multiple documents"),
    title: str | None = Form(None, description="Ontology title (default: first filename stem)"),
    description: str | None = Form(None, description="Ontology description"),
    ontology_language: str = Form("en", description="ISO 639-1 language for the ontology (all class/instance names and descriptions in this language)"),
    run_inference: bool = Query(True, description="Run LLM relation inference after extraction"),
    sequential: bool = Query(True, description="Use 3-stage sequential extraction (Bakker B)"),
    run_reasoning: bool = Query(True, description="Run OWL 2 RL reasoning after extraction"),
    parallel: bool = Query(True, description="Process chunks in parallel (4 workers); if False, sequential"),
):
    """Upload one or more documents and run the theory-grounded ontology pipeline.

    Provide either `file` (single) or `files` (multiple). Returns the merged graph
    and a full pipeline report with per-chunk stats.
    """
    uploads = _normalize_files(file=file, files=files)
    if not uploads:
        raise HTTPException(400, "Provide at least one document: use 'file' or 'files'")

    for u in uploads:
        suffix = Path(u.filename or "").suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise HTTPException(
                400, f"Unsupported format for {u.filename}. Use one of: {', '.join(_ALLOWED_SUFFIXES)}"
            )

    logger.info("[BuildOntology] files=%s inference=%s sequential=%s parallel=%s reasoning=%s",
                [u.filename for u in uploads], run_inference, sequential, parallel, run_reasoning)

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    temp_paths: list[Path] = []
    doc_names: list[str] = []

    try:
        for u in uploads:
            suffix = Path(u.filename or "").suffix.lower()
            unique_name = f"{uuid.uuid4().hex}{suffix}"
            tp = _DOCUMENTS_RAW / unique_name
            content = await u.read()
            tp.write_bytes(content)
            temp_paths.append(tp)
            doc_names.append(u.filename or unique_name)

        graph = None
        all_reports: list[dict[str, Any]] = []
        for i, (tp, doc_name) in enumerate(zip(temp_paths, doc_names)):
            _graph, report = await asyncio.to_thread(
                process_document,
                str(tp),
                run_inference=run_inference,
                verbose=False,
                sequential=sequential,
                run_reasoning=run_reasoning,
                parallel_extraction=parallel,
                ontology_language=ontology_language or "en",
            )
            if graph is None:
                graph = _graph
            else:
                graph.merge_from(_graph)
            all_reports.append(report.to_dict())

        if graph is None or not all_reports:
            raise HTTPException(500, "Pipeline produced no result")

        kb_id = uuid.uuid4().hex
        first_stem = Path(doc_names[0]).stem if doc_names else ""
        name = (title or first_stem or f"ontology-{kb_id[:8]}").strip() or f"ontology-{kb_id[:8]}"
        saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        _ONTOLOGY_GRAPHS.mkdir(parents=True, exist_ok=True)
        set_graph(graph, document_subject=None)
        save_to_path_with_metadata(
            saved_path,
            name=name,
            kb_id=kb_id,
            description=description or "",
            documents=doc_names,
            ontology_language=ontology_language or "en",
        )
        set_current_kb_id(kb_id)
        await asyncio.to_thread(_persist_vis_data, saved_path, graph)
        await asyncio.to_thread(build_qa_index, graph, False, saved_path)

        last_report_dict = all_reports[-1]
        export = graph.export()
        final_stats = export.get("stats", {})
        combined = _build_report_dict(
            last_report_dict,
            name,
            totals=final_stats,
            document_display=", ".join(doc_names) if len(doc_names) > 1 else (doc_names[0] if doc_names else ""),
            all_reports=all_reports if len(all_reports) > 1 else None,
            doc_names=doc_names if len(doc_names) > 1 else None,
        )

        return BuildOntologyResponse(
            graph=export,
            kb_id=kb_id,
            pipeline_report=PipelineReportResponse(
                document_path=combined.get("document_path", ""),
                total_chunks=combined.get("total_chunks", 0),
                totals=combined.get("totals", final_stats),
                extraction_totals=combined.get("extraction_totals", {}),
                llm_inferred_relations=combined.get("llm_inferred_relations", 0),
                reasoning=combined.get("reasoning", {}),
                elapsed_seconds=combined.get("elapsed_seconds", 0.0),
                extraction_mode=combined.get("extraction_mode", ""),
                chunk_stats=combined.get("chunk_stats", []),
                ontology_name=name,
                quality=combined.get("quality"),
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
        for tp in temp_paths:
            if tp.exists():
                try:
                    tp.unlink()
                except OSError:
                    pass


def _sse_event(data: dict) -> str:
    """Format dict as SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _apply_env_overrides(
    model: str | None = None,
    workers: int | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    temperature: float | None = None,
) -> dict[str, str | None]:
    """Apply form overrides to environment for pipeline execution.

    Returns the previous env values for later restore. Clears settings cache.
    """
    old_env = {
        "ONTOLOGY_LLM_MODEL": os.environ.get("ONTOLOGY_LLM_MODEL"),
        "CHUNK_SIZE": os.environ.get("CHUNK_SIZE"),
        "CHUNK_OVERLAP": os.environ.get("CHUNK_OVERLAP"),
        "LLM_PARALLEL_WORKERS": os.environ.get("LLM_PARALLEL_WORKERS"),
        "LLM_TEMPERATURE": os.environ.get("LLM_TEMPERATURE"),
    }
    if model:
        os.environ["ONTOLOGY_LLM_MODEL"] = model
    if workers is not None:
        os.environ["LLM_PARALLEL_WORKERS"] = str(workers)
    if chunk_size is not None:
        os.environ["CHUNK_SIZE"] = str(chunk_size)
    if chunk_overlap is not None:
        os.environ["CHUNK_OVERLAP"] = str(chunk_overlap)
    if temperature is not None:
        os.environ["LLM_TEMPERATURE"] = str(temperature)
    get_settings.cache_clear()
    return old_env


def _restore_env(old_env: dict[str, str | None]) -> None:
    """Restore environment from snapshot and clear settings cache."""
    for key, val in old_env.items():
        if val is not None:
            os.environ[key] = val
        elif key in os.environ:
            del os.environ[key]
    get_settings.cache_clear()


def _build_report_dict(
    report_dict: dict[str, Any],
    ontology_name: str,
    totals: dict[str, Any] | None = None,
    document_display: str | None = None,
    all_reports: list[dict[str, Any]] | None = None,
    doc_names: list[str] | None = None,
    health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build pipeline_report dict for SSE complete event.

    If totals is None, uses report_dict.get('totals', {}).
    Normalizes totals so 'relations' is set from 'edges' when missing (e.g. from graph.export() stats).
    If all_reports and doc_names are provided (multi-doc), aggregates total_chunks and chunk_stats
    across all documents and sets document_path to comma-separated doc names.
    """
    raw_totals = totals if totals is not None else report_dict.get("totals", {})
    totals_normalized = dict(raw_totals)
    if "relations" not in totals_normalized and "edges" in totals_normalized:
        totals_normalized["relations"] = totals_normalized["edges"]

    if all_reports and doc_names and len(doc_names) > 1:
        total_chunks = sum(r.get("total_chunks", 0) for r in all_reports)
        chunk_stats: list[dict[str, Any]] = []
        for doc_idx, r in enumerate(all_reports):
            for cs in r.get("chunk_stats", []):
                entry = dict(cs)
                entry["doc_index"] = doc_idx + 1
                entry["document"] = doc_names[doc_idx] if doc_idx < len(doc_names) else ""
                chunk_stats.append(entry)
        document_path = ", ".join(doc_names)
        # Use last report for inference/reasoning/elapsed (they apply to the merged run)
        last = all_reports[-1] if all_reports else report_dict
        return {
            "document_path": document_path,
            "total_chunks": total_chunks,
            "totals": totals_normalized,
            "extraction_totals": last.get("extraction_totals", {}),
            "llm_inferred_relations": last.get("llm_inferred_relations", 0),
            "reasoning": last.get("reasoning", {}),
            "elapsed_seconds": sum(r.get("elapsed_seconds", 0) for r in all_reports),
            "extraction_mode": last.get("extraction_mode", ""),
            "chunk_stats": chunk_stats,
            "ontology_name": ontology_name,
            "quality": last.get("quality"),
            "health": health,
        }
    return {
        "document_path": document_display or report_dict.get("document_path", ""),
        "total_chunks": report_dict.get("total_chunks", 0),
        "totals": totals_normalized,
        "extraction_totals": report_dict.get("extraction_totals", {}),
        "llm_inferred_relations": report_dict.get("llm_inferred_relations", 0),
        "reasoning": report_dict.get("reasoning", {}),
        "elapsed_seconds": report_dict.get("elapsed_seconds", 0.0),
        "extraction_mode": report_dict.get("extraction_mode", ""),
        "chunk_stats": report_dict.get("chunk_stats", []),
        "ontology_name": ontology_name,
        "quality": report_dict.get("quality"),
        "health": health,
    }


def _streaming_sse_headers() -> dict[str, str]:
    """SSE response headers for streaming endpoints."""
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@router.post("/build_ontology_stream")
async def build_ontology_stream(
    request: Request,
    file: UploadFile | None = File(None, description="Single document (PDF, DOCX, TXT, MD)"),
    files: list[UploadFile] | None = File(None, description="Multiple documents"),
    title: str | None = Form(None, description="Ontology title (default: first filename stem)"),
    description: str | None = Form(None, description="Ontology description"),
    ontology_language: str = Form("en", description="ISO 639-1 language for the ontology (all names/descriptions in this language)"),
    model: str | None = Form(None, description="LLM model override (e.g. gpt-4.1o-mini)"),
    workers: int | None = Form(None, description="Parallel workers for extraction"),
    chunk_size: int | None = Form(None, description="Chunk size in chars"),
    chunk_overlap: int | None = Form(None, description="Overlap between chunks"),
    temperature: float | None = Form(None, description="LLM sampling temperature"),
    run_inference: bool = Query(True, description="Run LLM relation inference after extraction"),
    sequential: bool = Query(True, description="Use 3-stage sequential extraction (Bakker B)"),
    run_reasoning: bool = Query(True, description="Run OWL 2 RL reasoning after extraction"),
    parallel: bool = Query(True, description="Process chunks in parallel; if False, sequential"),
):
    """Upload one or more documents and run the pipeline, streaming progress via SSE.

    Provide either `file` (single) or `files` (multiple). Response is text/event-stream.
    Each event is JSON: {step, data} for progress, or {type: "complete", ...} for the final result.
    """
    uploads = _normalize_files(file=file, files=files)
    if not uploads:
        raise HTTPException(400, "Provide at least one document: use 'file' or 'files'")

    for u in uploads:
        suffix = Path(u.filename or "").suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise HTTPException(
                400, f"Unsupported format for {u.filename}. Use one of: {', '.join(_ALLOWED_SUFFIXES)}"
            )

    logger.info("[BuildOntologyStream] files=%s", [u.filename for u in uploads])

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    temp_paths: list[Path] = []
    doc_names: list[str] = []

    try:
        for u in uploads:
            suffix = Path(u.filename or "").suffix.lower()
            unique_name = f"{uuid.uuid4().hex}{suffix}"
            tp = _DOCUMENTS_RAW / unique_name
            content = await u.read()
            tp.write_bytes(content)
            temp_paths.append(tp)
            doc_names.append(u.filename or unique_name)
    except Exception as e:
        logger.exception("Failed to save uploads")
        raise HTTPException(500, f"Failed to save files: {e}") from e

    progress_queue: Queue = Queue()
    cancel_event = threading.Event()

    def progress_callback(step: str, data: dict) -> None:
        progress_queue.put({"step": step, "data": data})

    async def watch_disconnect() -> None:
        """Set cancel_event when client disconnects (e.g. Cancel button)."""
        try:
            while True:
                message = await request.receive()
                if message.get("type") == "http.disconnect":
                    logger.info("[BuildOntologyStream] Client disconnected, cancelling pipeline")
                    cancel_event.set()
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def generate() -> Any:
        loop = asyncio.get_event_loop()
        result_holder: dict | None = None
        error_holder: str | None = None
        job_id = uuid.uuid4().hex
        _active_pipelines[job_id] = cancel_event

        extraction_mode = "legacy" if not sequential else ("parallel" if parallel else "sequential")
        yield _sse_event({
            "type": "job_started",
            "job_id": job_id,
            "extraction_mode": extraction_mode,
            "file_count": len(temp_paths),
        })

        disconnect_task = asyncio.create_task(watch_disconnect())

        def run_pipeline() -> None:
            nonlocal result_holder, error_holder
            old_env = _apply_env_overrides(
                model=model,
                workers=workers,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                temperature=temperature,
            )
            try:
                graph = None
                all_reports: list[dict[str, Any]] = []
                for i, (tp, doc_name) in enumerate(zip(temp_paths, doc_names)):
                    if cancel_event.is_set():
                        raise PipelineCancelledError("Cancelled by client")
                    if len(temp_paths) > 1:
                        progress_queue.put({
                            "step": "file_start",
                            "data": {
                                "file_index": i + 1,
                                "total_files": len(temp_paths),
                                "filename": doc_name,
                            },
                        })
                    _graph, report = process_document(
                        str(tp),
                        run_inference=run_inference,
                        verbose=False,
                        sequential=sequential,
                        run_reasoning=run_reasoning,
                        parallel_extraction=parallel,
                        progress_callback=progress_callback,
                        cancel_check=cancel_event.is_set,
                        ontology_language=ontology_language or "en",
                    )
                    if graph is None:
                        graph = _graph
                    else:
                        graph.merge_from(_graph)
                    all_reports.append(report.to_dict())

                if graph is None or not all_reports:
                    raise ValueError("Pipeline produced no result")

                kb_id = uuid.uuid4().hex
                first_stem = Path(doc_names[0]).stem if doc_names else ""
                name = (title or first_stem or f"ontology-{kb_id[:8]}").strip() or f"ontology-{kb_id[:8]}"
                saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
                _ONTOLOGY_GRAPHS.mkdir(parents=True, exist_ok=True)
                set_graph(graph, document_subject=None)
                save_to_path_with_metadata(
                    saved_path,
                    name=name,
                    kb_id=kb_id,
                    description=description or "",
                    documents=doc_names,
                    ontology_language=ontology_language or "en",
                )
                set_current_kb_id(kb_id)
                _persist_vis_data(saved_path, graph)
                build_qa_index(graph, False, saved_path)

                last_report_dict = all_reports[-1]
                export = graph.export()
                try:
                    health_result = compute_graph_health(graph, kb_id=kb_id)
                except Exception:
                    health_result = None
                result_holder = {
                    "type": "complete",
                    "graph": export,
                    "kb_id": kb_id,
                    "pipeline_report": _build_report_dict(
                        last_report_dict,
                        name,
                        totals=export.get("stats", {}),
                        document_display=", ".join(doc_names) if len(doc_names) > 1 else (doc_names[0] if doc_names else ""),
                        all_reports=all_reports if len(all_reports) > 1 else None,
                        doc_names=doc_names if len(doc_names) > 1 else None,
                        health=health_result,
                    ),
                }
            except PipelineCancelledError:
                logger.info("[BuildOntologyStream] Pipeline cancelled")
                error_holder = "Cancelled by user"
            except Exception as e:
                logger.exception("Pipeline failed")
                error_holder = str(e)
            finally:
                _restore_env(old_env)
                _active_pipelines.pop(job_id, None)
                for tp in temp_paths:
                    if tp.exists():
                        try:
                            tp.unlink()
                        except OSError:
                            pass
                progress_queue.put({"type": "end"})

        pipeline_task = asyncio.create_task(asyncio.to_thread(run_pipeline))

        pipeline_timeout = get_settings().pipeline_timeout_seconds
        while True:
            try:
                item = await asyncio.wait_for(
                    loop.run_in_executor(None, progress_queue.get),
                    timeout=pipeline_timeout,
                )
            except asyncio.TimeoutError:
                yield _sse_event({"type": "error", "message": "Pipeline timeout"})
                break

            if item.get("type") == "end":
                break

            yield _sse_event({"step": item["step"], "data": item["data"]})

        disconnect_task.cancel()
        try:
            await disconnect_task
        except asyncio.CancelledError:
            pass

        await pipeline_task
        if error_holder:
            yield _sse_event({"type": "error", "message": error_holder})
        elif result_holder:
            yield _sse_event(result_holder)

    async def body() -> Any:
        async for chunk in generate():
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=_streaming_sse_headers(),
    )


@router.post("/knowledge-bases/{kb_id}/extend_stream")
async def extend_kb_stream(
    kb_id: str,
    request: Request,
    file: UploadFile | None = File(None, description="Single document (PDF, DOCX, TXT, MD)"),
    files: list[UploadFile] | None = File(None, description="Multiple documents"),
    model: str | None = Form(None, description="LLM model override (e.g. gpt-4.1o-mini)"),
    workers: int | None = Form(None, description="Parallel workers for extraction"),
    chunk_size: int | None = Form(None, description="Chunk size in chars"),
    chunk_overlap: int | None = Form(None, description="Overlap between chunks"),
    temperature: float | None = Form(None, description="LLM sampling temperature"),
    run_inference: bool = Query(True),
    sequential: bool = Query(True),
    run_reasoning: bool = Query(True),
    parallel: bool = Query(True),
):
    """Upload one or more documents and merge their extracted ontologies into an existing KB, streaming progress via SSE."""
    kb_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not kb_path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")

    uploads = _normalize_files(file=file, files=files)
    if not uploads:
        raise HTTPException(400, "Provide at least one document: use 'file' or 'files'")

    for u in uploads:
        suffix = Path(u.filename or "").suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise HTTPException(
                400, f"Unsupported format for {u.filename}. Use one of: {', '.join(_ALLOWED_SUFFIXES)}"
            )

    logger.info("[ExtendKBStream] kb_id=%s files=%s", kb_id, [u.filename for u in uploads])

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    temp_paths: list[Path] = []
    doc_names: list[str] = []

    try:
        for u in uploads:
            suffix = Path(u.filename or "").suffix.lower()
            unique_name = f"{uuid.uuid4().hex}{suffix}"
            tp = _DOCUMENTS_RAW / unique_name
            content = await u.read()
            tp.write_bytes(content)
            temp_paths.append(tp)
            doc_names.append(u.filename or unique_name)
    except Exception as e:
        logger.exception("Failed to save uploads")
        raise HTTPException(500, f"Failed to save files: {e}") from e

    # Read existing metadata before entering the thread (including ontology language for extend)
    meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
    try:
        existing_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        existing_meta = {}
    kb_name = existing_meta.get("name", kb_id)
    kb_description = existing_meta.get("description", "")
    kb_ontology_language = existing_meta.get("ontology_language", "en")

    progress_queue: Queue = Queue()
    cancel_event = threading.Event()

    def progress_callback(step: str, data: dict) -> None:
        progress_queue.put({"step": step, "data": data})

    async def watch_disconnect() -> None:
        try:
            while True:
                message = await request.receive()
                if message.get("type") == "http.disconnect":
                    logger.info("[ExtendKBStream] Client disconnected, cancelling")
                    cancel_event.set()
                    break
        except (asyncio.CancelledError, Exception):
            pass

    async def generate() -> Any:
        loop = asyncio.get_event_loop()
        result_holder: dict | None = None
        error_holder: str | None = None
        job_id = uuid.uuid4().hex
        _active_pipelines[job_id] = cancel_event

        extraction_mode = "legacy" if not sequential else ("parallel" if parallel else "sequential")
        yield _sse_event({
            "type": "job_started",
            "job_id": job_id,
            "extraction_mode": extraction_mode,
            "file_count": len(temp_paths),
        })

        disconnect_task = asyncio.create_task(watch_disconnect())

        def run_extend() -> None:
            nonlocal result_holder, error_holder
            old_env = _apply_env_overrides(
                model=model,
                workers=workers,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                temperature=temperature,
            )
            try:
                existing_graph = load_from_path(kb_path)
                all_reports: list[dict[str, Any]] = []

                for i, (tp, doc_name) in enumerate(zip(temp_paths, doc_names)):
                    if cancel_event.is_set():
                        raise PipelineCancelledError("Cancelled by client")
                    if len(temp_paths) > 1:
                        progress_queue.put({
                            "step": "file_start",
                            "data": {
                                "file_index": i + 1,
                                "total_files": len(temp_paths),
                                "filename": doc_name,
                            },
                        })
                    new_graph, report = process_document(
                        str(tp),
                        run_inference=run_inference,
                        verbose=False,
                        sequential=sequential,
                        run_reasoning=run_reasoning,
                        parallel_extraction=parallel,
                        progress_callback=progress_callback,
                        cancel_check=cancel_event.is_set,
                        ontology_language=kb_ontology_language,
                    )
                    existing_graph.merge_from(new_graph)
                    all_reports.append(report.to_dict())

                set_graph(existing_graph, document_subject=None)

                saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
                save_to_path_with_metadata(
                    saved_path,
                    name=kb_name,
                    kb_id=kb_id,
                    description=kb_description,
                    documents=doc_names,
                    merge_documents=True,
                )
                set_current_kb_id(kb_id)
                _persist_vis_data(saved_path, existing_graph)
                build_qa_index(existing_graph, False, saved_path)

                last_report_dict = all_reports[-1] if all_reports else {}
                export = existing_graph.export()
                try:
                    health_result = compute_graph_health(existing_graph, kb_id=kb_id)
                except Exception:
                    health_result = None
                result_holder = {
                    "type": "complete",
                    "graph": export,
                    "kb_id": kb_id,
                    "pipeline_report": _build_report_dict(
                        last_report_dict,
                        kb_name,
                        totals=export.get("stats", {}),
                        document_display=", ".join(doc_names) if len(doc_names) > 1 else (doc_names[0] if doc_names else ""),
                        all_reports=all_reports if len(all_reports) > 1 else None,
                        doc_names=doc_names if len(doc_names) > 1 else None,
                        health=health_result,
                    ),
                }
            except PipelineCancelledError:
                logger.info("[ExtendKBStream] Pipeline cancelled")
                error_holder = "Cancelled by user"
            except Exception as e:
                logger.exception("Extend pipeline failed")
                error_holder = str(e)
            finally:
                _restore_env(old_env)
                _active_pipelines.pop(job_id, None)
                for tp in temp_paths:
                    if tp.exists():
                        try:
                            tp.unlink()
                        except OSError:
                            pass
                progress_queue.put({"type": "end"})

        pipeline_task = asyncio.create_task(asyncio.to_thread(run_extend))

        pipeline_timeout = get_settings().pipeline_timeout_seconds
        while True:
            try:
                item = await asyncio.wait_for(
                    loop.run_in_executor(None, progress_queue.get),
                    timeout=pipeline_timeout,
                )
            except asyncio.TimeoutError:
                yield _sse_event({"type": "error", "message": "Pipeline timeout"})
                break

            if item.get("type") == "end":
                break

            yield _sse_event({"step": item["step"], "data": item["data"]})

        disconnect_task.cancel()
        try:
            await disconnect_task
        except asyncio.CancelledError:
            pass

        await pipeline_task
        if error_holder:
            yield _sse_event({"type": "error", "message": error_holder})
        elif result_holder:
            yield _sse_event(result_holder)

    async def body() -> Any:
        async for chunk in generate():
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=_streaming_sse_headers(),
    )


@router.post("/knowledge-bases/{kb_id}/enrich_stream")
async def enrich_kb_stream(
    kb_id: str,
    request: Request,
    max_queries: int | None = Query(None, description="Override auto-computed query cap"),
    min_fidelity: float = Query(0.3, description="Drop results below this fidelity score (0–1)"),
    use_llm_content_score: bool = Query(True, description="Batch-score pages via LLM for objective relevance+quality"),
):
    """Run web enrichment on a knowledge base: infer queries from graph, fetch web pages, build doc, merge into graph. Streams progress via SSE."""
    try:
        kb_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        if not kb_path.exists():
            raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")

        from ontology_builder.enrichment import enrich_graph

        logger.info("[EnrichKBStream] kb_id=%s max_queries=%s min_fidelity=%s", kb_id, max_queries, min_fidelity)

        progress_queue: Queue = Queue()
        cancel_event = threading.Event()

        def progress_callback(step: str, data: dict) -> None:
            progress_queue.put({"step": step, "data": data})

        async def watch_disconnect() -> None:
            try:
                while True:
                    message = await request.receive()
                    if message.get("type") == "http.disconnect":
                        logger.info("[EnrichKBStream] Client disconnected")
                        cancel_event.set()
                        break
            except (asyncio.CancelledError, Exception):
                pass

        async def generate() -> Any:
            loop = asyncio.get_event_loop()
            result_holder: dict | None = None
            error_holder: str | None = None
            job_id = uuid.uuid4().hex
            _active_pipelines[job_id] = cancel_event

            yield _sse_event({
                "type": "job_started",
                "job_id": job_id,
                "job_type": "enrich",
            })

            disconnect_task = asyncio.create_task(watch_disconnect())

            def run_enrich() -> None:
                nonlocal result_holder, error_holder
                try:
                    graph = load_from_path(kb_path)
                    set_graph(graph, document_subject=None)
                    set_current_kb_id(kb_id)
                    report = enrich_graph(
                        graph,
                        kb_path=kb_path,
                        max_queries=max_queries,
                        min_fidelity=min_fidelity,
                        use_llm_content_score=use_llm_content_score,
                        verbose=True,
                        progress_callback=progress_callback,
                        cancel_check=cancel_event.is_set,
                    )
                    set_graph(graph, document_subject=None)
                    _persist_vis_data(kb_path, graph)
                    build_qa_index(graph, False, kb_path)

                    export = graph.export()
                    try:
                        health_result = compute_graph_health(graph, kb_id=kb_id)
                    except Exception:
                        health_result = None

                    pr = report.pipeline_report
                    result_holder = {
                        "type": "complete",
                        "graph": export,
                        "kb_id": kb_id,
                        "enrichment_report": {
                            "queries": report.queries,
                            "queries_count": len(report.queries),
                            "pages_fetched": report.pages_fetched,
                            "doc_path": str(report.doc_path),
                            "nodes_added": pr.nodes_added,
                            "nodes_updated": pr.nodes_updated,
                            "edges_added": pr.edges_added,
                            "axioms_added": pr.axioms_added,
                            "dp_added": pr.dp_added,
                            "merge_skipped": pr.merge_skipped,
                            "skip_reason": pr.skip_reason,
                            "analysis": pr.analysis,
                        },
                        "pipeline_report": _build_report_dict(
                            {},
                            "",
                            totals=export.get("stats", {}),
                            document_display=str(report.doc_path),
                            health=health_result,
                        ),
                    }
                except PipelineCancelledError:
                    logger.info("[EnrichKBStream] Enrichment cancelled")
                    error_holder = "Cancelled by user"
                except Exception as e:
                    logger.exception("Web enrichment failed")
                    error_holder = str(e)
                finally:
                    _active_pipelines.pop(job_id, None)
                    progress_queue.put({"type": "end"})

            pipeline_task = asyncio.create_task(asyncio.to_thread(run_enrich))

            pipeline_timeout = get_settings().pipeline_timeout_seconds
            while True:
                try:
                    item = await asyncio.wait_for(
                        loop.run_in_executor(None, progress_queue.get),
                        timeout=pipeline_timeout,
                    )
                except asyncio.TimeoutError:
                    yield _sse_event({"type": "error", "message": "Enrichment timeout"})
                    break

                if item.get("type") == "end":
                    break

                yield _sse_event({"step": item["step"], "data": item["data"]})

            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass

            try:
                await pipeline_task
            except Exception as e:
                logger.exception("Enrich pipeline task failed")
                error_holder = str(e)

            if error_holder:
                yield _sse_event({"type": "error", "message": error_holder})
            elif result_holder:
                yield _sse_event(result_holder)

        async def body() -> Any:
            async for chunk in generate():
                yield chunk

        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers=_streaming_sse_headers(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Enrich stream setup failed")
        raise HTTPException(500, f"Enrichment failed: {e}") from e


@router.post("/cancel_job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel an active pipeline job by ID."""
    cancel_event = _active_pipelines.get(job_id)
    if cancel_event is None:
        raise HTTPException(404, f"Job '{job_id}' not found or already completed.")
    cancel_event.set()
    logger.info("[CancelJob] Cancelled job %s", job_id)
    return {"status": "cancelled", "job_id": job_id}


@router.get("/knowledge-bases")
async def list_kb():
    """List persisted knowledge bases. Returns fresh data; no caching."""
    items = list_knowledge_bases()
    kb_items = [
        KnowledgeBaseItem(
            id=it["id"],
            name=it["name"],
            description=it.get("description", ""),
            created_at=it["created_at"],
            stats=it.get("stats", {}),
            documents=it.get("documents", []),
            ontology_language=it.get("ontology_language", "en"),
        )
        for it in items
    ]
    resp = KnowledgeBasesResponse(
        items=kb_items,
        active_id=get_current_kb_id(),
    )
    return JSONResponse(
        content=resp.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
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
        await asyncio.to_thread(build_qa_index, graph, False, path)
        return {"status": "ok", "active_id": kb_id}
    except Exception as e:
        logger.exception("Failed to load knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to load knowledge base: {e}") from e


class KBUpdateRequest(BaseModel):
    name: str | None = Field(None, description="New name for the knowledge base")
    description: str | None = Field(None, description="New description")
    ontology_language: str | None = Field(None, description="ISO 639-1 language of the ontology (metadata only; does not re-extract)")


@router.patch("/knowledge-bases/{kb_id}")
async def update_kb(kb_id: str, req: KBUpdateRequest):
    """Update knowledge base metadata (name, description, ontology_language)."""
    from ontology_builder.storage.graph_store import update_kb_metadata
    try:
        meta = update_kb_metadata(
            kb_id,
            name=req.name,
            description=req.description,
            ontology_language=req.ontology_language,
        )
        return {"status": "ok", "kb_id": kb_id, "name": meta.get("name"), "description": meta.get("description")}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        logger.exception("Failed to update KB %s", kb_id)
        raise HTTPException(500, f"Failed to update: {e}") from e


@router.delete("/knowledge-bases/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base entirely: graph JSON, metadata, QA index, and in-memory state."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
    index_path = _ONTOLOGY_GRAPHS / f"{kb_id}_index.npz"
    index_path_legacy = _ONTOLOGY_GRAPHS / f"{kb_id}.qa_index.npz"
    records_path = _ONTOLOGY_GRAPHS / f"{kb_id}.qa_records.json"
    vis_path = _ONTOLOGY_GRAPHS / f"{kb_id}.vis.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    try:
        path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        index_path.unlink(missing_ok=True)
        index_path_legacy.unlink(missing_ok=True)
        records_path.unlink(missing_ok=True)
        vis_path.unlink(missing_ok=True)
        if get_current_kb_id() == kb_id:
            clear_graph_store()
            clear_qa_index()
            set_current_kb_id(None)
            clear_last_active_kb()
        logger.info("[DeleteKB] Deleted knowledge base kb_id=%s path=%s", kb_id, path)
        return {"status": "ok", "deleted_id": kb_id}
    except OSError as e:
        logger.exception("Failed to delete knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to delete: {e}") from e


_REPORTS_DIR = _REPO_ROOT / "documents" / "reports"


@router.get("/knowledge-bases/{kb_id}/health")
async def get_kb_health(kb_id: str):
    """Return graph health metrics for a knowledge base."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    try:
        from ontology_builder.evaluation.graph_health import (
            compute_graph_health,
            load_graph_health,
            save_graph_health,
        )
        graph = await asyncio.to_thread(
            load_from_path, path, False
        )
        health = compute_graph_health(graph, kb_id=kb_id)
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(save_graph_health, kb_id, health, _REPORTS_DIR)
        return health
    except Exception as e:
        logger.exception("Failed to compute health for kb_id=%s: %s", kb_id, e)
        raise HTTPException(500, f"Failed to compute health: {e}") from e


@router.get("/knowledge-bases/{kb_id}/repair-diagnosis")
async def get_repair_diagnosis(kb_id: str):
    """Return graph health, gaps (missing definitions), and repair recommendations."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    try:
        from ontology_builder.evaluation.graph_health import compute_graph_health
        from ontology_builder.repair.gap_repair import detect_gaps_in_graph
        graph = await asyncio.to_thread(load_from_path, path, False)
        health = compute_graph_health(graph, kb_id=kb_id)
        gaps = detect_gaps_in_graph(graph, kb_path=path, max_gaps=20)
        s = health.get("structural", {})
        orphans = s.get("orphan_nodes", 0)
        components = s.get("connected_components", 1)
        n = s.get("node_count", 0)
        recommendations = []
        if orphans > 0:
            recommendations.append({"id": "orphans", "title": "Link orphan nodes", "desc": f"{orphans} nodes have no connections. Repair will link them to similar nodes via embeddings.", "action": "structural"})
        if components > 1:
            recommendations.append({"id": "components", "title": "Bridge disconnected components", "desc": f"Graph has {components} separate subgraphs. Repair will add bridges to the largest component.", "action": "structural"})
        if gaps:
            recommendations.append({"id": "gaps", "title": "Fill missing definitions", "desc": f"{len(gaps)} concepts lack descriptions. Enable Internet definition repair to search the web.", "action": "internet", "gaps": gaps[:10]})
        if n > 0 and not recommendations:
            recommendations.append({"id": "healthy", "title": "Graph looks healthy", "desc": "No major structural issues detected. Repair can still add root concept and run inference.", "action": "optional"})
        return {
            "kb_id": kb_id,
            "health": health,
            "gaps": gaps,
            "gaps_count": len(gaps),
            "recommendations": recommendations,
        }
    except Exception as e:
        logger.exception("Failed to get repair diagnosis for kb_id=%s: %s", kb_id, e)
        raise HTTPException(500, f"Failed: {e}") from e


@router.get("/knowledge-bases/{kb_id}/evaluation-records")
async def get_evaluation_records(kb_id: str):
    """Return list of evaluation records for a knowledge base (timestamp, scores, per-question details)."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    records_file = _REPORTS_DIR / f"eval-records-{kb_id}.json"
    if not records_file.exists():
        return []
    try:
        records = json.loads(records_file.read_text(encoding="utf-8"))
        return records if isinstance(records, list) else []
    except Exception as e:
        logger.warning("Failed to load eval records for kb_id=%s: %s", kb_id, e)
        return []


@router.get("/knowledge-bases/{kb_id}/repair-records")
async def get_repair_records(kb_id: str):
    """Return list of repair records for a knowledge base (timestamp, edges, gaps, iterations, config)."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    records_file = _REPORTS_DIR / f"repair-records-{kb_id}.json"
    if not records_file.exists():
        return []
    try:
        records = json.loads(records_file.read_text(encoding="utf-8"))
        return records if isinstance(records, list) else []
    except Exception as e:
        logger.warning("Failed to load repair records for kb_id=%s: %s", kb_id, e)
        return []


def _save_repair_record(
    kb_id: str,
    kb_name: str,
    repair_internet_definitions: bool,
    repair_iterations: int,
    min_fidelity: float,
    report,
) -> None:
    """Persist repair record to repair-records-{kb_id}.json (same pattern as eval records)."""
    import uuid
    from datetime import datetime, timezone
    record = {
        "id": str(uuid.uuid4()),
        "kb_id": kb_id,
        "kb_name": kb_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repair_internet_definitions": repair_internet_definitions,
        "repair_iterations": repair_iterations,
        "min_fidelity": min_fidelity,
        "edges_added": report.edges_added,
        "gaps_repaired": report.gaps_repaired,
        "iterations_completed": report.iterations_completed,
        "iteration_summaries": report.iteration_summaries,
        "health_before": report.health_before,
        "health_after": report.health_after,
        "definitions_added": getattr(report, "definitions_added", None) or {},
        "inferred_edges": [list(e) for e in getattr(report, "inferred_edges", [])],
    }
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    records_file = _REPORTS_DIR / f"repair-records-{kb_id}.json"
    records: list[dict] = []
    if records_file.exists():
        try:
            records = json.loads(records_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    records.insert(0, record)
    records = records[:50]
    records_file.write_text(json.dumps(records, indent=2), encoding="utf-8")


@router.post("/knowledge-bases/{kb_id}/repair")
async def repair_kb(
    kb_id: str,
    repair_internet_definitions: bool = Query(False, description="Search web for missing concept definitions"),
    repair_iterations: int = Query(1, ge=1, le=5, description="Number of repair iterations (1–5)"),
    min_fidelity: float = Query(0.3, ge=0.0, le=1.0, description="Confidence threshold for web definitions (0–1); filters low-quality sources"),
):
    """Repair graph: optional internet definition fill, link orphans, bridge components. Returns SSE stream."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")

    def gen():
        import traceback
        from queue import Queue, Empty
        import threading

        queue: Queue = Queue()
        result_holder: dict | None = None
        error_holder: str | None = None

        def run_repair():
            nonlocal result_holder, error_holder
            try:
                from ontology_builder.repair import RepairConfig, repair_graph
                graph = load_from_path(path)
                meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"

                def progress(step: str, message: str, details: dict) -> None:
                    queue.put({"type": "step", "step": step, "message": message, **details})

                config = RepairConfig(
                    run_reasoning_after=True,
                    repair_internet_definitions=repair_internet_definitions,
                    repair_iterations=repair_iterations,
                    min_fidelity=min_fidelity,
                )
                report = repair_graph(
                    graph,
                    config=config,
                    progress_callback=progress,
                    kb_id=kb_id,
                    kb_path=str(path),
                )
                set_graph(graph, document_subject=None)
                set_current_kb_id(kb_id)
                build_qa_index(graph, False, path)
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    save_to_path_with_metadata(path, name=meta.get("name", kb_id), kb_id=kb_id, description=meta.get("description", ""), documents=meta.get("documents"))
                else:
                    meta = {}
                    save_to_path(path)
                _persist_vis_data(path, graph)
                kb_name = meta.get("name", kb_id)
                _save_repair_record(
                    kb_id=kb_id,
                    kb_name=kb_name,
                    repair_internet_definitions=repair_internet_definitions,
                    repair_iterations=repair_iterations,
                    min_fidelity=min_fidelity,
                    report=report,
                )
                result_holder = {
                    "edges_added": report.edges_added,
                    "gaps_repaired": report.gaps_repaired,
                    "iterations_completed": report.iterations_completed,
                    "iteration_summaries": report.iteration_summaries,
                    "definitions_added": report.definitions_added,
                    "inferred_edges": [list(e) for e in report.inferred_edges],
                }
            except Exception as e:
                logger.exception("Repair failed for kb_id=%s", kb_id)
                error_holder = str(e)
            finally:
                queue.put({"type": "_done"})

        thread = threading.Thread(target=run_repair)
        thread.start()

        while True:
            try:
                item = queue.get(timeout=0.5)
            except Empty:
                if not thread.is_alive():
                    break
                continue
            if item.get("type") == "_done":
                break
            if item.get("type") == "step":
                msg = item.get("message", "")
                it = item.get("iteration")
                tot = item.get("iteration_total")
                if it and tot and tot > 1:
                    msg = f"[{it}/{tot}] {msg}"
                rescan = item.get("rescan")
                payload = {"type": "step", "message": msg, "step": item.get("step"), "iteration": it, "iteration_total": tot}
                if rescan:
                    payload["rescan"] = rescan
                yield f"data: {json.dumps(payload)}\n\n"

        if error_holder:
            yield f"data: {json.dumps({'type': 'error', 'message': error_holder})}\n\n"
        elif result_holder:
            yield f"data: {json.dumps({'type': 'done', **result_holder})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
        },
    )


def _run_evaluation_sync(
    path: Path,
    kb_id: str,
    kb_name: str,
    num_questions: int,
    reports_dir: Path,
) -> dict:
    """Run evaluation in sync (for thread pool). Returns record dict."""
    from ontology_builder.evaluation.eval_pipeline import run_evaluation
    graph = load_from_path(path, seed_canonicalizer=False)
    record = run_evaluation(
        graph,
        kb_id=kb_id,
        kb_name=kb_name,
        num_questions=num_questions,
        reports_dir=str(reports_dir),
        progress_callback=None,
        kb_path=path,
    )
    return record.to_dict()


@router.post("/knowledge-bases/{kb_id}/evaluate")
async def evaluate_kb(
    kb_id: str,
    num_questions: int = Query(5, ge=1, le=500, description="Number of evaluation questions"),
):
    """Run QA evaluation: generate questions, answer, compute scores. Returns SSE stream."""
    path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
    if not path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
    kb_name = kb_id
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            kb_name = meta.get("name", kb_id)
        except Exception:
            pass

    async def gen():
        import traceback
        yield f"data: {json.dumps({'type': 'step', 'message': 'Loading knowledge base'})}\n\n"
        yield f"data: {json.dumps({'type': 'step', 'message': 'Building index'})}\n\n"
        yield f"data: {json.dumps({'type': 'step', 'message': 'Generating questions'})}\n\n"
        try:
            record = await asyncio.to_thread(
                _run_evaluation_sync,
                path,
                kb_id,
                kb_name,
                num_questions,
                _REPORTS_DIR,
            )
            per_q = record.get("scores", {}).get("per_question", [])
            yield f"data: {json.dumps({'type': 'step', 'message': f'Generated {len(per_q)} questions'})}\n\n"
            for i, pq in enumerate(per_q):
                yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': len(per_q), 'question': pq.get('question', '')})}\n\n"
            yield f"data: {json.dumps({'type': 'step', 'message': 'Computing final scores'})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'scores': record.get('scores', {}), 'health': record.get('health', {}), 'record': record})}\n\n"
        except Exception as e:
            logger.exception("Evaluate failed for kb_id=%s", kb_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'traceback': traceback.format_exc()})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
        },
    )


_FORMAT_TO_MIME: dict[str, tuple[str, str]] = {
    "turtle": ("text/turtle", ".ttl"),
    "ttl": ("text/turtle", ".ttl"),
    "json-ld": ("application/ld+json", ".jsonld"),
    "jsonld": ("application/ld+json", ".jsonld"),
    "xml": ("application/rdf+xml", ".owl"),
    "rdf+xml": ("application/rdf+xml", ".owl"),
    "owl": ("application/rdf+xml", ".owl"),
    "nt": ("application/n-triples", ".nt"),
}


@router.get("/ontology/export")
async def export_ontology(
    format: str = Query("turtle", description="Export format: turtle, json-ld, xml"),
    kb_id: str | None = Query(None, description="Knowledge base ID. Uses active KB if omitted."),
):
    """Export the ontology and entire knowledge base to a reusable standard format.

    Supported formats (W3C standards):
    - **turtle** (default): Human-readable, compact RDF. Best for sharing and version control.
    - **json-ld**: JSON-based Linked Data. Best for integration with JSON systems.
    - **xml**: RDF/XML. Classic format, widely supported by ontology tools.

    The export includes classes, instances, relations, data properties, and axioms
    in OWL 2 / RDF form, suitable for import into Protégé, GraphDB, or any RDF store.
    """
    graph = get_graph()
    ontology_label: str | None = None
    if kb_id:
        path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
        if not path.exists():
            raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                ontology_label = meta.get("name", kb_id)
            except (json.JSONDecodeError, OSError):
                ontology_label = kb_id
        else:
            ontology_label = kb_id
    else:
        if graph is None:
            raise HTTPException(404, "No ontology. Build one or specify kb_id.")
        active = get_current_kb_id()
        if active:
            meta_path = _ONTOLOGY_GRAPHS / f"{active}.meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    ontology_label = meta.get("name", active)
                except (json.JSONDecodeError, OSError):
                    ontology_label = active
            else:
                ontology_label = active

    fmt = format.lower().strip()
    if fmt not in _FORMAT_TO_MIME:
        raise HTTPException(
            400,
            f"Unsupported format: {format}. Use: turtle, json-ld, xml",
        )
    mime, ext = _FORMAT_TO_MIME[fmt]

    try:
        content = await asyncio.to_thread(
            export_ontology_to_rdf,
            graph,
            format=fmt,
            ontology_label=ontology_label,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if isinstance(content, bytes):
        body = content
    else:
        body = content.encode("utf-8")

    filename = (ontology_label or "ontology").replace(" ", "_") + ext
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/qa/ask", response_model=QASourceResponse)
async def qa_ask(
    req: QAAskRequest,
    retrieval_mode: str = Query("context", description="'context' (ontology-grounded), 'hyperedges', or 'snippets'"),
):
    """Answer a question using ontology-grounded RAG retrieval with attribution."""
    logger.info("[QA] question=%r mode=%s kb_id=%s", req.question[:80], retrieval_mode, req.kb_id)
    kb_id = req.kb_id or get_current_kb_id()
    if kb_id and kb_id != get_current_kb_id():
        path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        if not path.exists():
            raise HTTPException(404, f"Ontology '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False, path)
        logger.info("[QA] Activated ontology %s for query", kb_id)
    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "No ontology graph. Select one from the sidebar or build one first.")

    def _retrieve():
        if retrieval_mode == "hyperedges":
            snippets = retrieve_hyperedges(req.question, 10, 5)
            return snippets, [f"he:{i}" for i in range(len(snippets))], ""
        result = retrieve_with_context(req.question, 10)
        onto = result.ontological_context if retrieval_mode == "context" else ""
        return result.facts, result.source_refs, onto

    context_snippets, source_refs, onto_ctx = await asyncio.to_thread(_retrieve)

    # If index is empty but we have a graph, the background build may not have finished.
    # Building the index for large graphs (1000+ nodes) can take 1-3 minutes — don't block the request.
    if not context_snippets and graph is not None and graph.get_graph().number_of_nodes() > 0:
        kb_path = _ONTOLOGY_GRAPHS / f"{get_current_kb_id()}.json" if get_current_kb_id() else None
        if kb_path is None or kb_path.exists():
            asyncio.create_task(asyncio.to_thread(build_qa_index, graph, False, kb_path))
            raise HTTPException(
                503,
                "QA index is building. For large graphs this takes 1-2 minutes. Please wait and try again.",
            )

    if not context_snippets:
        raise HTTPException(503, "QA index is empty. Rebuild the ontology.")

    try:
        qa_result = await asyncio.to_thread(
            answer_question,
            req.question,
            context_snippets,
            source_refs,
            onto_ctx,
            answer_language=req.answer_language,
        )
    except Exception as e:
        logger.exception("QA LLM failed")
        raise HTTPException(500, f"Answer generation failed: {e}") from e

    source_labels = [source_ref_to_label(r) for r in qa_result.sources]
    return QASourceResponse(
        answer=qa_result.answer,
        reasoning=qa_result.reasoning,
        sources=context_snippets,
        source_refs=qa_result.sources,
        source_labels=source_labels,
        ontological_context=qa_result.ontological_context,
        num_facts_used=qa_result.num_facts_used,
        kb_id=get_current_kb_id(),
    )


@router.get("/graph", response_model=GraphExportResponse)
async def get_current_graph():
    """Return the current graph export with class/instance/edge/axiom counts (no embeddings)."""
    data = get_export_for_api()
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
    kb_id = get_current_kb_id()
    kb_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json" if kb_id else None
    await asyncio.to_thread(build_qa_index, graph, False, kb_path)

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
async def graph_viewer(
    kb_id: str | None = Query(None, description="Knowledge base ID. Uses active KB if omitted."),
    node: str | None = Query(None, description="Pre-select and highlight this node by ID."),
    depth: int = Query(1, ge=1, le=5, description="N-hop depth for subgraph highlight (1-5)."),
    debug: bool = Query(False, description="Enable console logging for layout debugging."),
):
    """Interactive vis.js graph viewer (standalone HTML page)."""
    if kb_id:
        path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        vis_path = _ONTOLOGY_GRAPHS / f"{kb_id}.vis.json"
        if not path.exists():
            raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
        if vis_path.exists() and vis_path.stat().st_mtime >= path.stat().st_mtime:
            html = await asyncio.to_thread(
                render_vis_from_file, vis_path, pre_select_node=node, depth=depth, debug=debug
            )
            return HTMLResponse(content=html)
        graph = await asyncio.to_thread(load_from_path, path, False)
        html = await asyncio.to_thread(
            generate_visjs_html, graph, node, depth, debug,
        )
        await asyncio.to_thread(_persist_vis_data, path, graph)
        return HTMLResponse(content=html)
    graph = get_graph()
    if graph is None:
        raise HTTPException(404, "No ontology graph. Select one from the sidebar or build one first.")
    html = generate_visjs_html(graph, pre_select_node=node, depth=depth, debug=debug)
    return HTMLResponse(content=html)


# Include agent QA routes
from ontology_builder.ui.chat_agent_routes import router as agent_router

router.include_router(agent_router)
