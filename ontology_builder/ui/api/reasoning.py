"""Reasoning apply endpoint."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from ontology_builder.qa.graph_index import build_index as build_qa_index
from ontology_builder.reasoning.engine import run_inference as apply_reasoning
from ontology_builder.storage.graph_store import get_graph, get_subject, set_graph

from ontology_builder.ui.api.schemas import ReasoningResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])


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
