"""Knowledge base CRUD endpoints."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ontology_builder.qa.graph_index import build_index as build_qa_index
from ontology_builder.storage.graph_store import (
    clear as clear_graph_store,
    get_current_kb_id,
    list_knowledge_bases,
    load_from_path,
    set_current_kb_id,
    set_graph,
    update_kb_metadata,
)

from ontology_builder.ui.api.common import get_ontology_graphs_dir
from ontology_builder.ui.api.schemas import KnowledgeBaseItem, KnowledgeBasesResponse, KBUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])

_ONTOLOGY_GRAPHS = get_ontology_graphs_dir()


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
        await asyncio.to_thread(build_qa_index, graph, False)
        return {"status": "ok", "active_id": kb_id}
    except Exception as e:
        logger.exception("Failed to load knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to load knowledge base: {e}") from e


@router.patch("/knowledge-bases/{kb_id}")
async def update_kb(kb_id: str, req: KBUpdateRequest):
    """Update knowledge base metadata (name, description)."""
    try:
        meta = update_kb_metadata(kb_id, name=req.name, description=req.description)
        return {
            "status": "ok",
            "kb_id": kb_id,
            "name": meta.get("name"),
            "description": meta.get("description"),
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        logger.exception("Failed to update KB %s", kb_id)
        raise HTTPException(500, f"Failed to update: {e}") from e


@router.delete("/knowledge-bases/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a persisted knowledge base."""
    from ontology_builder.qa.graph_index import clear_index as clear_qa_index

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
            clear_qa_index()
            set_current_kb_id(None)
        return {"status": "ok", "deleted_id": kb_id}
    except OSError as e:
        logger.exception("Failed to delete knowledge base %s", kb_id)
        raise HTTPException(500, f"Failed to delete: {e}") from e
