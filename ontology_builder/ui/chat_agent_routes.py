"""Agent QA routes: POST /qa/agent/ask for multi-step KB exploration."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from queue import Queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ontology_builder.agent.agent_controller import KnowledgeAgent
from ontology_builder.qa.answer import source_ref_to_label
from ontology_builder.qa.graph_index import build_index as build_qa_index
from ontology_builder.storage.graph_store import (
    get_current_kb_id,
    get_graph,
    get_ontology_graphs_dir,
    load_from_path,
    set_current_kb_id,
    set_graph,
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder-agent"])


class AgentAskRequest(BaseModel):
    """Request body for agent QA."""

    question: str = Field(..., description="User question")
    kb_id: str | None = Field(None, description="Knowledge base ID. Uses active KB if omitted.")
    answer_language: str | None = Field(None, description="ISO 639-1 for answer language")
    assistant_mode: bool = Field(False, description="If True, only return final answer (reasoning in logs)")


class AgentAskResponse(BaseModel):
    """Agent QA response with session_id for reasoning viewer."""

    answer: str = Field(..., description="Generated answer")
    reasoning: str = Field("", description="Reasoning text")
    sources: list[str] = Field(default_factory=list, description="Fact strings used")
    source_refs: list[str] = Field(default_factory=list, description="Source reference IDs")
    source_labels: list[str] = Field(default_factory=list, description="Human-readable labels")
    num_facts_used: int = Field(0, description="Number of facts used")
    kb_id: str | None = Field(None, description="KB that was queried")
    session_id: str = Field("", description="Session ID for reasoning viewer")
    steps: list[dict] = Field(default_factory=list, description="Exploration steps")
    gaps: list[dict] = Field(default_factory=list, description="Detected ontology gaps")


@router.get("/qa/agent/reasoning/{session_id}")
async def get_reasoning_log(session_id: str):
    """Fetch reasoning log by session ID for the reasoning viewer."""
    from ontology_builder.agent.reasoning_logger import load_reasoning_log

    log = load_reasoning_log(session_id)
    if log is None:
        raise HTTPException(404, "Reasoning log not found")
    return log


@router.post("/qa/agent/ask", response_model=AgentAskResponse)
async def qa_agent_ask(req: AgentAskRequest):
    """Answer using multi-step KB exploration (Graph-of-Thought agent)."""
    logger.info("[Agent] question=%r kb_id=%s assistant_mode=%s", req.question[:80], req.kb_id, req.assistant_mode)

    kb_id = req.kb_id or get_current_kb_id()
    if kb_id and kb_id != get_current_kb_id():
        graphs_dir = get_ontology_graphs_dir()
        path = graphs_dir / f"{kb_id}.json"
        if not path.exists():
            raise HTTPException(404, f"Ontology '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False, path)
        logger.info("[Agent] Activated ontology %s", kb_id)

    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "No ontology graph. Select one from the sidebar or build one first.")

    agent = KnowledgeAgent(kb_id=kb_id or get_current_kb_id(), assistant_mode=req.assistant_mode)

    try:
        result = await asyncio.to_thread(
            agent.answer,
            req.question,
            answer_language=req.answer_language,
        )
    except Exception as e:
        logger.exception("[Agent] Answer failed")
        raise HTTPException(500, f"Agent failed: {e}") from e

    source_labels = [source_ref_to_label(r) for r in result.source_refs]

    return AgentAskResponse(
        answer=result.answer,
        reasoning=result.reasoning,
        sources=result.sources,
        source_refs=result.source_refs,
        source_labels=source_labels,
        num_facts_used=result.num_facts_used,
        kb_id=get_current_kb_id(),
        session_id=result.session_id,
        steps=result.steps,
        gaps=result.gaps,
    )


@router.post("/qa/agent/ask/stream")
async def qa_agent_ask_stream(req: AgentAskRequest):
    """Stream reasoning steps during agent execution, then return full result."""
    logger.info("[Agent stream] question=%r kb_id=%s", req.question[:80], req.kb_id)

    kb_id = req.kb_id or get_current_kb_id()
    if kb_id and kb_id != get_current_kb_id():
        graphs_dir = get_ontology_graphs_dir()
        path = graphs_dir / f"{kb_id}.json"
        if not path.exists():
            raise HTTPException(404, f"Ontology '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False, path)
        logger.info("[Agent stream] Activated ontology %s", kb_id)

    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "No ontology graph. Select one from the sidebar or build one first.")

    agent = KnowledgeAgent(kb_id=kb_id or get_current_kb_id(), assistant_mode=req.assistant_mode)
    queue: Queue[tuple[str, object]] = Queue()

    def run_agent():
        try:
            result = agent.answer(
                req.question,
                answer_language=req.answer_language,
                on_step=lambda step: queue.put(("step", step)),
            )
            source_labels = [source_ref_to_label(r) for r in result.source_refs]
            payload = {
                "answer": result.answer,
                "reasoning": result.reasoning,
                "sources": result.sources,
                "source_refs": result.source_refs,
                "source_labels": source_labels,
                "num_facts_used": result.num_facts_used,
                "kb_id": get_current_kb_id(),
                "session_id": result.session_id,
                "steps": result.steps,
                "gaps": result.gaps,
            }
            queue.put(("done", payload))
        except Exception as e:
            queue.put(("error", {"message": str(e)}))

    async def event_stream():
        thread = threading.Thread(target=run_agent)
        thread.start()
        while True:
            msg_type, payload = await asyncio.to_thread(queue.get)
            if msg_type == "step":
                yield f"data: {json.dumps({'type': 'step', 'step': payload})}\n\n"
            elif msg_type == "done":
                yield f"data: {json.dumps({'type': 'done', 'result': payload})}\n\n"
                break
            elif msg_type == "error":
                yield f"data: {json.dumps({'type': 'error', **payload})}\n\n"
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
