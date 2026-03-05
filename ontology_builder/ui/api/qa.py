"""QA ask endpoint for ontology API."""

import logging

import asyncio
from fastapi import APIRouter, HTTPException, Query

from ontology_builder.qa.answer import answer_question, source_ref_to_label
from ontology_builder.qa.graph_index import (
    build_index as build_qa_index,
    retrieve_hyperedges,
    retrieve_with_context,
)
from ontology_builder.storage.graph_store import (
    get_current_kb_id,
    get_graph,
    load_from_path,
    set_current_kb_id,
    set_graph,
)

from ontology_builder.storage.graph_store import get_ontology_graphs_dir
from ontology_builder.ui.api.schemas import QAAskRequest, QASourceResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])


@router.post("/qa/ask", response_model=QASourceResponse)
async def qa_ask(
    req: QAAskRequest,
    retrieval_mode: str = Query(
        "context",
        description="'context' (ontology-grounded), 'hyperedges', or 'snippets'",
    ),
):
    """Answer a question using ontology-grounded RAG retrieval with attribution."""
    logger.info("[QA] question=%r mode=%s kb_id=%s", req.question[:80], retrieval_mode, req.kb_id)
    kb_id = req.kb_id or get_current_kb_id()
    if kb_id and kb_id != get_current_kb_id():
        path = get_ontology_graphs_dir() / f"{kb_id}.json"
        if not path.exists():
            raise HTTPException(404, f"Ontology '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False)
        logger.info("[QA] Activated ontology %s for query", kb_id)
    graph = get_graph()
    if graph is None:
        raise HTTPException(
            503,
            "No ontology graph. Select one from the sidebar or build one first.",
        )

    if retrieval_mode == "hyperedges":
        context_snippets = await asyncio.to_thread(
            retrieve_hyperedges,
            req.question,
            10,
            5,
        )
        source_refs = [f"he:{i}" for i in range(len(context_snippets))]
        onto_ctx = ""
    elif retrieval_mode == "context":
        result = await asyncio.to_thread(retrieve_with_context, req.question, 10)
        context_snippets = result.facts
        source_refs = result.source_refs
        onto_ctx = result.ontological_context
    else:
        result = await asyncio.to_thread(retrieve_with_context, req.question, 10)
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

    source_labels = [source_ref_to_label(r) for r in qa_result.sources]
    return QASourceResponse(
        answer=qa_result.answer,
        sources=context_snippets,
        source_refs=qa_result.sources,
        source_labels=source_labels,
        ontological_context=qa_result.ontological_context,
        num_facts_used=qa_result.num_facts_used,
        kb_id=get_current_kb_id(),
    )
