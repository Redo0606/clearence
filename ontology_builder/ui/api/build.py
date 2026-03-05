"""Build ontology and extend KB streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from queue import Queue

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from ontology_builder.pipeline.run_pipeline import PipelineCancelledError, process_document
from ontology_builder.qa.graph_index import build_index as build_qa_index
from ontology_builder.storage.graph_store import (
    get_ontology_graphs_dir,
    load_from_path,
    save_to_path_with_metadata,
    set_current_kb_id,
    set_graph,
)

from ontology_builder.ui.api.common import (
    apply_env_overrides,
    build_report_dict,
    get_active_pipelines,
    get_allowed_suffixes,
    get_documents_raw,
    restore_env,
    sse_event,
    streaming_sse_headers,
)
from ontology_builder.ui.api.schemas import BuildOntologyResponse, PipelineReportResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])

_DOCUMENTS_RAW = get_documents_raw()
_ONTOLOGY_GRAPHS = get_ontology_graphs_dir()
_ALLOWED_SUFFIXES = get_allowed_suffixes()
_active_pipelines = get_active_pipelines()


@router.post("/build_ontology", response_model=BuildOntologyResponse)
async def build_ontology(
    file: UploadFile = File(..., description="Document (PDF, DOCX, TXT, MD)"),
    title: str | None = Form(None, description="Ontology title (default: filename stem)"),
    description: str | None = Form(None, description="Ontology description"),
    run_inference: bool = Query(True, description="Run LLM relation inference after extraction"),
    sequential: bool = Query(True, description="Use 3-stage sequential extraction (Bakker B)"),
    run_reasoning: bool = Query(True, description="Run OWL 2 RL reasoning after extraction"),
    parallel: bool = Query(True, description="Process chunks in parallel (4 workers); if False, sequential"),
):
    """Upload a document and run the theory-grounded ontology pipeline."""
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported format. Use one of: {', '.join(_ALLOWED_SUFFIXES)}")

    logger.info(
        "[BuildOntology] file=%s inference=%s sequential=%s parallel=%s reasoning=%s",
        file.filename,
        run_inference,
        sequential,
        parallel,
        run_reasoning,
    )

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
            parallel_extraction=parallel,
        )
        set_graph(graph, document_subject=None)
        await asyncio.to_thread(build_qa_index, graph, False)

        kb_id = uuid.uuid4().hex
        name = (
            (title or Path(file.filename).stem or f"ontology-{kb_id[:8]}").strip()
            or f"ontology-{kb_id[:8]}"
        )
        saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        _ONTOLOGY_GRAPHS.mkdir(parents=True, exist_ok=True)
        save_to_path_with_metadata(
            saved_path,
            name=name,
            kb_id=kb_id,
            description=description or "",
            documents=[file.filename] if file.filename else [],
        )
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


@router.post("/build_ontology_stream")
async def build_ontology_stream(
    request: Request,
    file: UploadFile = File(..., description="Document (PDF, DOCX, TXT, MD)"),
    title: str | None = Form(None, description="Ontology title (default: filename stem)"),
    description: str | None = Form(None, description="Ontology description"),
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
    """Upload a document and run the pipeline, streaming progress via SSE."""
    import threading

    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported format. Use one of: {', '.join(_ALLOWED_SUFFIXES)}")

    logger.info("[BuildOntologyStream] file=%s", file.filename)

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = _DOCUMENTS_RAW / unique_name

    try:
        content = await file.read()
        temp_path.write_bytes(content)
    except Exception as e:
        logger.exception("Failed to save upload")
        raise HTTPException(500, f"Failed to save file: {e}") from e

    progress_queue: Queue = Queue()
    cancel_event = threading.Event()

    def progress_callback(step: str, data: dict) -> None:
        progress_queue.put({"step": step, "data": data})

    async def watch_disconnect() -> None:
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
        yield sse_event({"type": "job_started", "job_id": job_id, "extraction_mode": extraction_mode})

        disconnect_task = asyncio.create_task(watch_disconnect())

        def run_pipeline() -> None:
            nonlocal result_holder, error_holder
            old_env = apply_env_overrides(
                model=model,
                workers=workers,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                temperature=temperature,
            )
            try:
                graph, report = process_document(
                    str(temp_path),
                    run_inference=run_inference,
                    verbose=False,
                    sequential=sequential,
                    run_reasoning=run_reasoning,
                    parallel_extraction=parallel,
                    progress_callback=progress_callback,
                    cancel_check=cancel_event.is_set,
                )
                set_graph(graph, document_subject=None)
                build_qa_index(graph, False)

                kb_id = uuid.uuid4().hex
                name = (
                    (title or Path(file.filename).stem or f"ontology-{kb_id[:8]}").strip()
                    or f"ontology-{kb_id[:8]}"
                )
                saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
                _ONTOLOGY_GRAPHS.mkdir(parents=True, exist_ok=True)
                save_to_path_with_metadata(
                    saved_path,
                    name=name,
                    kb_id=kb_id,
                    description=description or "",
                    documents=[file.filename] if file.filename else [],
                )
                set_current_kb_id(kb_id)

                report_dict = report.to_dict()
                result_holder = {
                    "type": "complete",
                    "graph": graph.export(),
                    "kb_id": kb_id,
                    "pipeline_report": build_report_dict(
                        report_dict, name, document_display=file.filename
                    ),
                }
            except PipelineCancelledError:
                logger.info("[BuildOntologyStream] Pipeline cancelled")
                error_holder = "Cancelled by user"
            except Exception as e:
                logger.exception("Pipeline failed")
                error_holder = str(e)
            finally:
                restore_env(old_env)
                _active_pipelines.pop(job_id, None)
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                progress_queue.put({"type": "end"})

        pipeline_task = asyncio.create_task(asyncio.to_thread(run_pipeline))

        while True:
            try:
                item = await asyncio.wait_for(
                    loop.run_in_executor(None, progress_queue.get),
                    timeout=300.0,
                )
            except asyncio.TimeoutError:
                yield sse_event({"type": "error", "message": "Pipeline timeout"})
                break

            if item.get("type") == "end":
                break

            yield sse_event({"step": item["step"], "data": item["data"]})

        disconnect_task.cancel()
        try:
            await disconnect_task
        except asyncio.CancelledError:
            pass

        await pipeline_task
        if error_holder:
            yield sse_event({"type": "error", "message": error_holder})
        elif result_holder:
            yield sse_event(result_holder)

    async def body() -> Any:
        async for chunk in generate():
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=streaming_sse_headers(),
    )


@router.post("/knowledge-bases/{kb_id}/extend_stream")
async def extend_kb_stream(
    kb_id: str,
    request: Request,
    file: UploadFile = File(..., description="Document (PDF, DOCX, TXT, MD)"),
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
    """Upload a document and merge its extracted ontology into an existing KB, streaming progress via SSE."""
    import threading

    kb_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
    if not kb_path.exists():
        raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")

    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported format. Use one of: {', '.join(_ALLOWED_SUFFIXES)}")

    logger.info("[ExtendKBStream] kb_id=%s file=%s", kb_id, file.filename)

    _DOCUMENTS_RAW.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = _DOCUMENTS_RAW / unique_name

    try:
        content = await file.read()
        temp_path.write_bytes(content)
    except Exception as e:
        logger.exception("Failed to save upload")
        raise HTTPException(500, f"Failed to save file: {e}") from e

    meta_path = _ONTOLOGY_GRAPHS / f"{kb_id}.meta.json"
    try:
        existing_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        existing_meta = {}
    kb_name = existing_meta.get("name", kb_id)
    kb_description = existing_meta.get("description", "")

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
        yield sse_event({"type": "job_started", "job_id": job_id, "extraction_mode": extraction_mode})

        disconnect_task = asyncio.create_task(watch_disconnect())

        def run_extend() -> None:
            nonlocal result_holder, error_holder
            old_env = apply_env_overrides(
                model=model,
                workers=workers,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                temperature=temperature,
            )
            try:
                existing_graph = load_from_path(kb_path)

                new_graph, report = process_document(
                    str(temp_path),
                    run_inference=run_inference,
                    verbose=False,
                    sequential=sequential,
                    run_reasoning=run_reasoning,
                    parallel_extraction=parallel,
                    progress_callback=progress_callback,
                    cancel_check=cancel_event.is_set,
                )

                existing_graph.merge_from(new_graph)
                set_graph(existing_graph, document_subject=None)
                build_qa_index(existing_graph, False)

                saved_path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
                save_to_path_with_metadata(
                    saved_path,
                    name=kb_name,
                    kb_id=kb_id,
                    description=kb_description,
                    documents=[file.filename] if file.filename else [],
                    merge_documents=True,
                )
                set_current_kb_id(kb_id)

                report_dict = report.to_dict()
                result_holder = {
                    "type": "complete",
                    "graph": existing_graph.export(),
                    "kb_id": kb_id,
                    "pipeline_report": build_report_dict(
                        report_dict,
                        kb_name,
                        totals=existing_graph.export().get("stats", {}),
                        document_display=file.filename,
                    ),
                }
            except PipelineCancelledError:
                logger.info("[ExtendKBStream] Pipeline cancelled")
                error_holder = "Cancelled by user"
            except Exception as e:
                logger.exception("Extend pipeline failed")
                error_holder = str(e)
            finally:
                restore_env(old_env)
                _active_pipelines.pop(job_id, None)
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                progress_queue.put({"type": "end"})

        pipeline_task = asyncio.create_task(asyncio.to_thread(run_extend))

        while True:
            try:
                item = await asyncio.wait_for(
                    loop.run_in_executor(None, progress_queue.get),
                    timeout=300.0,
                )
            except asyncio.TimeoutError:
                yield sse_event({"type": "error", "message": "Pipeline timeout"})
                break

            if item.get("type") == "end":
                break

            yield sse_event({"step": item["step"], "data": item["data"]})

        disconnect_task.cancel()
        try:
            await disconnect_task
        except asyncio.CancelledError:
            pass

        await pipeline_task
        if error_holder:
            yield sse_event({"type": "error", "message": error_holder})
        elif result_holder:
            yield sse_event(result_holder)

    async def body() -> Any:
        async for chunk in generate():
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=streaming_sse_headers(),
    )


@router.post("/cancel_job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel an active pipeline job by ID."""
    cancel_event = _active_pipelines.get(job_id)
    if cancel_event is None:
        raise HTTPException(404, f"Job '{job_id}' not found or already completed.")
    cancel_event.set()
    logger.info("[CancelJob] Cancelled job %s", job_id)
    return {"status": "cancelled", "job_id": job_id}
