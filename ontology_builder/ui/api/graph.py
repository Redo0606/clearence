"""Graph and export endpoints."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from ontology_builder.export.owl_exporter import export_ontology_to_rdf
from ontology_builder.storage.graph_store import (
    get_current_kb_id,
    get_export,
    get_graph,
    get_ontology_graphs_dir,
    load_from_path,
)
from ontology_builder.ui.graph_viewer import generate_visjs_html, visualize

from ontology_builder.ui.api.schemas import GraphExportResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ontology-builder"])

_ONTOLOGY_GRAPHS = get_ontology_graphs_dir()
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
    """Export the ontology and entire knowledge base to a reusable standard format."""
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
):
    """Interactive vis.js graph viewer (standalone HTML page)."""
    graph = get_graph()
    if kb_id:
        path = _ONTOLOGY_GRAPHS / f"{kb_id}.json"
        if not path.exists():
            raise HTTPException(404, f"Knowledge base '{kb_id}' not found.")
        graph = await asyncio.to_thread(load_from_path, path)
    if graph is None:
        raise HTTPException(
            404,
            "No ontology graph. Select one from the sidebar or build one first.",
        )
    html = generate_visjs_html(graph)
    return HTMLResponse(content=html)
