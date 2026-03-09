"""Reasoning viewer: load and display reasoning logs (steps, graph, gaps)."""

from __future__ import annotations

from typing import Any

from ontology_builder.agent.reasoning_logger import load_reasoning_log


def get_reasoning_data(session_id: str) -> dict[str, Any] | None:
    """Load reasoning log for a session. Returns None if not found."""
    return load_reasoning_log(session_id)


def format_reasoning_for_display(log: dict[str, Any]) -> str:
    """Format reasoning log as readable markdown for UI display."""
    lines = []

    lines.append("## Query")
    lines.append(log.get("query", ""))

    lines.append("\n## Exploration Steps")
    for i, step in enumerate(log.get("steps", []), 1):
        q = step.get("question", "")
        a = step.get("answer", "")
        lines.append(f"\n### Step {i}: {q}")
        lines.append(a[:500] + "..." if len(a) > 500 else a)

    graph = log.get("graph", {})
    if graph:
        lines.append("\n## Reasoning Graph")
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if nodes:
            lines.append("\n**Concepts:** " + ", ".join(n.get("concept", "") for n in nodes))
        if edges:
            lines.append("\n**Relations:**")
            for e in edges[:20]:
                lines.append(f"  - {e.get('source', '')} --[{e.get('relation', '')}]--> {e.get('target', '')}")

    gaps = log.get("gaps", [])
    if gaps:
        lines.append("\n## Ontology Gaps")
        for g in gaps:
            lines.append(f"  - {g.get('description', g)}")

    lines.append("\n## Final Answer")
    lines.append(log.get("answer", ""))

    return "\n".join(lines)
