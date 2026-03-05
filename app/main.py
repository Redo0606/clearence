"""FastAPI app entry point. Mounts PDF-to-OWL and living-ontology routers."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import ontology
from ontology_builder.ui.api import router as graph_router

logger = logging.getLogger(__name__)


class FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after each emit for immediate output in Docker."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def _configure_logging() -> None:
    """Configure application-wide logging with detailed format for step-by-step tracing."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    format_str = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )
    handler = FlushingStreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    # Reduce noise from third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # Suppress verbose pdfminer DEBUG (PS parser, PDF interpreter)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)


app = FastAPI(title="PDF to Ontology API", description="Convert PDF field documentation to OWL/RDF via LLM (LM Studio or OpenAI)")

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


@app.get("/")
async def read_root():
    """Return service info: name, docs URL, health URL."""
    return {"service": "PDF to Ontology", "docs": "/docs", "health": "/health"}


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