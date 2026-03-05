"""FastAPI app entry point. Mounts PDF-to-OWL and living-ontology routers."""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.logging_config import configure_table_logging
from app.routers import ontology
from ontology_builder.qa.graph_index import build_index as build_qa_index
from ontology_builder.storage.graph_store import (
    get_ontology_graphs_dir,
    list_knowledge_bases,
    load_from_path,
    set_current_kb_id,
    set_graph,
)
from ontology_builder.ui.api import router as graph_router
from ontology_builder.ui.chat_ui import generate_chat_ui_html

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure application-wide logging with table format. INFO by default."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    configure_table_logging(level=level)
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Skip GET /health spam
    logging.getLogger("ontology_builder.llm.client").setLevel(logging.INFO)


app = FastAPI(
    title="Theory-Grounded Ontology Graph API",
    description=(
        "Build formal, theory-grounded ontologies from documents using sequential LLM extraction "
        "(Bakker Approach B), OWL 2 RL reasoning (Smith & Proietti), and ontology-grounded RAG "
        "(OntoRAG + OG-RAG). Supports LM Studio and OpenAI."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ontology.router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    _configure_logging()
    settings = get_settings()
    logger.info("Ontology API starting | log_level=%s | LLM=%s | model=%s",
                settings.log_level, settings.openai_base_url, settings.ontology_llm_model)
    try:
        kb_items = list_knowledge_bases()
        if not kb_items:
            return
        latest = kb_items[0]
        kb_id = latest.get("id")
        if not kb_id:
            return
        kb_path = get_ontology_graphs_dir() / f"{kb_id}.json"
        if not kb_path.exists():
            return
        graph = await asyncio.to_thread(load_from_path, kb_path)
        set_graph(graph, document_subject=None)
        set_current_kb_id(kb_id)
        await asyncio.to_thread(build_qa_index, graph, False)
        logger.info("Restored KB on startup | kb_id=%s", kb_id)
    except Exception as e:
        logger.warning("Failed to restore latest KB on startup: %s", e)


@app.get("/")
async def read_root():
    """Return service info: name, docs URL, health URL."""
    return {"service": "PDF to Ontology", "docs": "/docs", "health": "/health", "app": "/app"}


@app.get("/app", response_class=HTMLResponse)
async def chat_app():
    """Serve the ontology chat UI."""
    return HTMLResponse(
        content=generate_chat_ui_html(),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


def run():
    """Start uvicorn server on 0.0.0.0:8000."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()