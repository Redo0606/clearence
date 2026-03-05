"""
In-memory store for the current ontology graph so reasoning and QA can use it.
Optional save/load to JSON for persistence. Supports multiple knowledge bases.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any

from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

_current_graph: OntologyGraph | None = None
_current_export: dict[str, Any] | None = None
_document_subject: str | None = None
_current_kb_id: str | None = None


def get_ontology_graphs_dir() -> Path:
    """Return the directory for persisted ontology graphs."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / "documents" / "ontology_graphs"


def set_current_kb_id(kb_id: str | None) -> None:
    """Set the ID of the currently active knowledge base."""
    global _current_kb_id
    _current_kb_id = kb_id


def get_current_kb_id() -> str | None:
    """Return the ID of the currently active knowledge base."""
    return _current_kb_id


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


def save_to_path_with_metadata(
    path: Path,
    name: str,
    kb_id: str,
    description: str = "",
) -> None:
    """Persist current graph export and metadata sidecar."""
    save_to_path(path)
    meta_path = path.with_suffix(".meta.json")
    meta = {
        "id": kb_id,
        "name": name,
        "description": description,
        "created_at": time.time(),
        "stats": get_export().get("stats", {}) if get_export() else {},
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def list_knowledge_bases() -> list[dict[str, Any]]:
    """List persisted knowledge bases from the ontology_graphs directory."""
    base_dir = get_ontology_graphs_dir()
    if not base_dir.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in base_dir.glob("*.json"):
        if path.suffix == ".json" and path.stem.endswith(".meta"):
            continue
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                result.append({
                    "id": meta.get("id", path.stem),
                    "name": meta.get("name", path.stem),
                    "description": meta.get("description", ""),
                    "created_at": meta.get("created_at", path.stat().st_mtime),
                    "stats": meta.get("stats", {}),
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("[GraphStore] Skipping invalid meta %s: %s", meta_path, e)
        else:
            result.append({
                "id": path.stem,
                "name": path.stem,
                "description": "",
                "created_at": path.stat().st_mtime,
                "stats": {},
            })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


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
    # NetworkX node-link payloads may use either "links" or "edges"
    # depending on version/configuration. Support both to avoid losing
    # relationships when loading persisted knowledge bases.
    links_data = data.get("links")
    if not isinstance(links_data, list):
        links_data = data.get("edges")
    if not isinstance(links_data, list):
        links_data = []
    index_to_id: list[str] = []
    for n in nodes_data:
        if not isinstance(n, dict):
            continue
        node_id = n.get("id", str(len(index_to_id)))
        node_type = n.get("type", "Entity")
        kind = n.get("kind", "class")
        desc = n.get("description", "")
        index_to_id.append(node_id)
        graph.add_entity(node_id, node_type, kind=kind, description=desc)
    for link in links_data:
        src = link.get("source", 0)
        tgt = link.get("target", 0)
        rel = link.get("relation", "related_to")
        conf = float(link.get("confidence", 1.0))
        if isinstance(src, int) and isinstance(tgt, int) and 0 <= src < len(index_to_id) and 0 <= tgt < len(index_to_id):
            src_id, tgt_id = index_to_id[src], index_to_id[tgt]
        elif isinstance(src, str) and isinstance(tgt, str):
            src_id, tgt_id = src, tgt
        else:
            continue
        graph.add_relation(src_id, rel, tgt_id, confidence=conf)
    for axiom in data.get("axioms", []):
        graph.add_axiom(axiom)
    for dp in data.get("data_properties", []):
        graph.add_data_property(dp.get("entity", ""), dp.get("attribute", ""), dp.get("value", ""), dp.get("datatype", "string"))
    return graph
