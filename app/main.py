"""FastAPI app entry point. Mounts PDF-to-OWL and living-ontology routers."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from core.config import EMBEDDING_PROVIDER_OPENAI, get_settings
from app.logging_config import configure_table_logging
from app.routers import ontology
from ontology_builder.embeddings import preload_embedding_model
from ontology_builder.qa.graph_index import build_index as build_qa_index, clear_index as clear_qa_index
from ontology_builder.storage.graph_store import (
    clear as clear_graph_store,
    get_last_active_kb,
    get_ontology_graphs_dir,
    load_from_path,
    set_current_kb_id,
    set_graph,
)
from ontology_builder.ui.api import router as graph_router
from ontology_builder.ui.chat_ui import generate_chat_ui_html

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: configure logging, preload embedding model, restore last active KB. Shutdown: clear store and index."""
    _configure_logging()
    settings = get_settings()
    logger.info(
        "Ontology API starting | log_level=%s | LLM=%s | model=%s",
        settings.log_level,
        settings.openai_base_url,
        settings.ontology_llm_model,
    )
    # Only preload when using local SentenceTransformer; with OpenAI embeddings no local model is loaded.
    if settings.embedding_provider != EMBEDDING_PROVIDER_OPENAI:
        await asyncio.to_thread(preload_embedding_model)
    else:
        logger.info("Embeddings: OpenAI (no local BERT/SentenceTransformer loaded)")
    last_id = get_last_active_kb()
    if last_id:
        graphs_dir = get_ontology_graphs_dir()
        path = graphs_dir / f"{last_id}.json"
        if path.exists():
            try:
                graph = load_from_path(path)
                set_graph(graph, document_subject=None)
                set_current_kb_id(last_id)
                await asyncio.to_thread(build_qa_index, graph, False)
                logger.info("Ontology API | restored active KB: %s", last_id)
            except Exception as e:
                logger.warning("Ontology API | failed to restore KB %s: %s", last_id, e)
    yield
    clear_graph_store()
    set_current_kb_id(None)
    clear_qa_index()
    logger.info("Ontology API shutdown | KB cleared")


def _configure_logging() -> None:
    """Configure application-wide logging with table format.

    Sets level from LOG_LEVEL, suppresses noisy loggers (httpx, openai, etc.).
    """
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
    title="Clearence · Theory-Grounded Ontology Graph API",
    description=(
        "Build formal, theory-grounded ontologies from documents using sequential LLM extraction "
        "(Bakker Approach B), OWL 2 RL reasoning (Smith & Proietti), and ontology-grounded RAG "
        "(OntoRAG + OG-RAG). Supports LM Studio and OpenAI. Developed and maintained by Reda Sarehane."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UI_STATIC = Path(__file__).resolve().parent.parent / "ontology_builder" / "ui" / "static"
app.mount("/static", StaticFiles(directory=str(_UI_STATIC)), name="static")

app.include_router(ontology.router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")


@app.get("/")
async def read_root():
    """Return service info: name, docs URL, health URL."""
    return {"service": "Clearence", "developer": "Reda Sarehane", "docs": "/docs", "health": "/health", "app": "/app"}


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


@app.get("/app/theme", response_class=HTMLResponse)
async def theme_preview():
    """Serve the theme design system preview page (injects :root from theme.py)."""
    from ontology_builder.ui.theme import get_css_root_block

    static_file = _UI_STATIC / "theme-preview.html"
    html = static_file.read_text(encoding="utf-8")
    root_style = f"<style>\n{get_css_root_block()}\n  </style>"
    return HTMLResponse(content=html.replace("</head>", f"{root_style}\n</head>", 1))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


def run() -> None:
    """Start uvicorn server on 0.0.0.0:8000 (entry point for ontology-app CLI)."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()