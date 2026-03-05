"""Table-style logging formatter for readable pipeline output."""

import logging
import re
import sys


# Map logger names to short component labels
_COMPONENT_MAP = {
    "ontology_builder.pipeline.loader": "Loader",
    "ontology_builder.pipeline.chunker": "Chunker",
    "ontology_builder.pipeline.run_pipeline": "Pipeline",
    "ontology_builder.pipeline.extractor": "Extractor",
    "ontology_builder.pipeline.ontology_builder": "Ontology",
    "ontology_builder.pipeline.relation_inferer": "RelationInfer",
    "ontology_builder.pipeline.taxonomy_builder": "Taxonomy",
    "ontology_builder.llm.client": "LLM",
    "ontology_builder.ui.api": "API",
    "ontology_builder.storage.graph_store": "GraphStore",
    "ontology_builder.qa.answer": "QA",
    "ontology_builder.qa.graph_index": "QAIndex",
    "ontology_builder.reasoning.engine": "Reasoning",
    "ontology_builder.storage.hypergraph": "Hypergraph",
    "app.main": "App",
    "app.routers.ontology": "Router",
}


def _component_from_name(name: str) -> str:
    """Derive short component label from logger name."""
    if name in _COMPONENT_MAP:
        return _COMPONENT_MAP[name]
    # Fallback: last part of dotted path, title-cased
    parts = name.split(".")
    last = parts[-1] if parts else name
    return last.title()[:12]


def _clean_message(msg: str) -> str:
    """Remove redundant [Component] prefix from message if present."""
    return re.sub(r"^\[[\w\s]+\]\s*", "", msg).strip()


class TableFormatter(logging.Formatter):
    """Format logs as aligned table columns: TIME | COMPONENT | LEVEL | MESSAGE."""

    COL_WIDTHS = (10, 14, 6)  # time, component, level

    def format(self, record: logging.LogRecord) -> str:
        time_str = self.formatTime(record, self.datefmt or "%H:%M:%S")
        component = _component_from_name(record.name)
        level = record.levelname
        msg = _clean_message(record.getMessage())

        # Pad columns for alignment
        time_pad = time_str.ljust(self.COL_WIDTHS[0])
        comp_pad = component.ljust(self.COL_WIDTHS[1])
        level_pad = level.ljust(self.COL_WIDTHS[2])

        return f"{time_pad} │ {comp_pad} │ {level_pad} │ {msg}"


class FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes only on INFO+ for immediate output in Docker, without flooding on DEBUG."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        # Flush only for important levels so Docker shows logs promptly; DEBUG can be buffered
        if record.levelno >= logging.INFO:
            self.flush()


def configure_table_logging(level: int = logging.INFO) -> None:
    """Configure root logger with table formatter and flushing handler."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()  # Replace uvicorn/default handlers with our table format
    handler = FlushingStreamHandler(sys.stdout)
    handler.setFormatter(TableFormatter(datefmt="%H:%M:%S"))
    root.addHandler(handler)
    # Force uvicorn loggers to propagate to root so they use our table formatter
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
