"""Chat UI: single-page app with chat, KB selector, and document upload."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

API_BASE = "/api/v1"

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"


def generate_chat_ui_html() -> str:
    """Generate standalone HTML page for the ontology chat interface."""
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))
    template = env.get_template("chat.html")
    css_content = (_STATIC_DIR / "chat.css").read_text(encoding="utf-8")
    js_content = (_STATIC_DIR / "chat.js").read_text(encoding="utf-8")
    return template.render(
        api_base=API_BASE,
        css_content=css_content,
        js_content=js_content,
    )
