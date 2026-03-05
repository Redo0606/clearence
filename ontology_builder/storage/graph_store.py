"""
In-memory store for the current ontology graph so reasoning and QA can use it.
Optional save/load to JSON for persistence.
"""
import json
import logging
from pathlib import Path
from typing import Any

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

_current_graph: OntologyGraph | None = None
_current_export: dict[str, Any] | None = None
_document_subject: str | None = None


def set_graph(graph: OntologyGraph, document_subject: str | None = None) -> None:
    """Set the current graph (and optional subject) after build."""
    global _current_graph, _current_export, _document_subject
    _current_graph = graph
    nodes = graph.get_graph().number_of_nodes()
    edges = graph.get_graph().number_of_edges()
    logger.info("[GraphStore] Graph stored | nodes=%d | edges=%d | document_subject=%s", nodes, edges, document_subject)
    _current_export = graph.export()
    _document_subject = document_subject


def get_graph() -> OntologyGraph | None:
    """Return the current graph, or None if none has been set."""
    return _current_graph


def get_export() -> dict[str, Any] | None:
    """Return the current graph as node-link export, or None."""
    return _current_export


def get_subject() -> str | None:
    """Return the document subject/domain if set."""
    return _document_subject


def clear() -> None:
    """Clear the stored graph (e.g. when invalidating QA index)."""
    global _current_graph, _current_export, _document_subject
    logger.debug("Graph store cleared")
    _current_graph = None
    _current_export = None
    _document_subject = None


def save_to_path(path: Path) -> None:
    """Persist current graph export to a JSON file."""
    data = get_export()
    if data is None:
        raise ValueError("No graph to save")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_from_path(path: Path) -> OntologyGraph:
    """Load an OntologyGraph from a node-link JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return _graph_from_export(data)


def _graph_from_export(data: dict[str, Any]) -> OntologyGraph:
    """Build OntologyGraph from node_link_data format.

    NetworkX node_link_data uses: nodes (list of dicts with id, type), links (source,
    target as indices or ids, relation). We support both index-based and id-based links.
    """
    graph = OntologyGraph()
    nodes_data = data.get("nodes", [])
    links_data = data.get("links", [])
    index_to_id: list[str] = []
    for n in nodes_data:
        if not isinstance(n, dict):
            continue
        node_id = n.get("id", str(len(index_to_id)))
        node_type = n.get("type", "Entity")
        index_to_id.append(node_id)
        graph.add_entity(node_id, node_type)
    for link in links_data:
        src = link.get("source", 0)
        tgt = link.get("target", 0)
        rel = link.get("relation", "related_to")
        # Handle both index-based (NetworkX default) and id-based links
        if isinstance(src, int) and isinstance(tgt, int) and 0 <= src < len(index_to_id) and 0 <= tgt < len(index_to_id):
            src_id, tgt_id = index_to_id[src], index_to_id[tgt]
        elif isinstance(src, str) and isinstance(tgt, str):
            src_id, tgt_id = src, tgt
        else:
            continue
        graph.add_relation(src_id, rel, tgt_id)
    return graph
