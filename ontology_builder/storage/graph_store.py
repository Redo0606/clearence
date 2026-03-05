"""In-memory store for the current ontology graph so reasoning and QA can use it.

Provides get/set/clear for the active graph and its node-link export. Optional
save/load to JSON for persistence. Supports multiple knowledge bases via
metadata sidecar files (.meta.json).

Thread-safety:
    Uses module-level globals (_current_graph, _current_export, etc.) for
    simplicity. This store is single-writer: concurrent writes (e.g. multiple
    build_ontology requests modifying the graph simultaneously) are NOT
    supported. Reads (get_graph, get_export) are safe when no write is in
    progress. For production multi-tenant use, consider a per-session or
    per-request graph store with proper locking.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any

from ontology_builder.ontology.canonicalizer import seed_from_entities
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
    documents: list[str] | None = None,
    merge_documents: bool = False,
) -> None:
    """Persist current graph export and metadata sidecar.

    Args:
        path: Path to save the graph JSON.
        name: Ontology name.
        kb_id: Knowledge base ID.
        description: Optional description.
        documents: List of document filenames. If merge_documents is True, appends to
            existing documents; otherwise replaces.
        merge_documents: If True and documents is provided, append to existing meta
            documents instead of replacing.
    """
    save_to_path(path)
    meta_path = path.with_suffix(".meta.json")
    stats = get_export().get("stats", {}) if get_export() else {}

    # Load existing meta to preserve created_at and optionally merge documents
    existing_meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            existing_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    created_at = existing_meta.get("created_at", time.time())
    existing_docs: list[str] = existing_meta.get("documents", [])

    if documents is not None:
        if merge_documents and existing_docs:
            # Deduplicate while preserving order
            seen = set(existing_docs)
            for d in documents:
                if d not in seen:
                    existing_docs.append(d)
                    seen.add(d)
            doc_list = existing_docs
        else:
            doc_list = list(documents)
    else:
        doc_list = existing_docs

    meta = {
        "id": kb_id,
        "name": name,
        "description": description,
        "created_at": created_at,
        "stats": stats,
        "documents": doc_list,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def update_kb_metadata(kb_id: str, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    """Update metadata (name, description) for a persisted knowledge base.
    Returns the updated meta dict.
    """
    base_dir = get_ontology_graphs_dir()
    meta_path = base_dir / f"{kb_id}.meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Knowledge base '{kb_id}' not found.")
    existing = json.loads(meta_path.read_text(encoding="utf-8"))
    if name is not None:
        existing["name"] = name
    if description is not None:
        existing["description"] = description
    meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def list_knowledge_bases() -> list[dict[str, Any]]:
    """List persisted knowledge bases from the ontology_graphs directory.

    Only includes entries where the main .json graph file exists. Uses path.stem
    as the canonical id (filename without extension) so lookups always match.
    """
    base_dir = get_ontology_graphs_dir()
    if not base_dir.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in base_dir.glob("*.json"):
        if path.suffix == ".json" and path.stem.endswith(".meta"):
            continue
        if not path.exists():
            continue
        kb_id = path.stem
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                result.append({
                    "id": kb_id,
                    "name": meta.get("name", kb_id),
                    "description": meta.get("description", ""),
                    "created_at": meta.get("created_at", path.stat().st_mtime),
                    "stats": meta.get("stats", {}),
                    "documents": meta.get("documents", []),
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("[GraphStore] Skipping invalid meta %s: %s", meta_path, e)
                result.append({
                    "id": kb_id,
                    "name": kb_id,
                    "description": "",
                    "created_at": path.stat().st_mtime,
                    "stats": {},
                    "documents": [],
                })
        else:
            result.append({
                "id": kb_id,
                "name": kb_id,
                "description": "",
                "created_at": path.stat().st_mtime,
                "stats": {},
                "documents": [],
            })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


def load_from_path(path: Path) -> OntologyGraph:
    """Load an OntologyGraph from a node-link JSON file.

    Seeds the canonicalizer with existing entity names for consistent
    deduplication when enriching the KB.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = _graph_from_export(data)
    entity_names = list(graph.get_graph().nodes())
    if entity_names:
        seed_from_entities(entity_names)
    return graph


def _graph_from_export(data: dict[str, Any]) -> OntologyGraph:
    """Build OntologyGraph from node_link_data format.

    NetworkX node_link_data uses: nodes (list of dicts with id, type), links (source,
    target as indices or ids, relation). We support both index-based and id-based links.
    Preserves provenance (source_documents), synonyms, and other attributes.
    """
    graph = OntologyGraph()
    nodes_data = data.get("nodes", [])
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
        extra = {k: v for k, v in n.items() if k not in ("id", "type", "kind", "description")}
        graph.add_entity(node_id, node_type, kind=kind, description=desc, **extra)
    for link in links_data:
        src = link.get("source", 0)
        tgt = link.get("target", 0)
        rel = link.get("relation", "related_to")
        conf = float(link.get("confidence", 1.0))
        # Support both NetworkX index-based (source/target as int) and id-based links
        if isinstance(src, int) and isinstance(tgt, int) and 0 <= src < len(index_to_id) and 0 <= tgt < len(index_to_id):
            src_id, tgt_id = index_to_id[src], index_to_id[tgt]
        elif isinstance(src, str) and isinstance(tgt, str):
            src_id, tgt_id = src, tgt
        else:
            continue
        extra = {k: v for k, v in link.items() if k not in ("source", "target", "relation", "confidence")}
        graph.add_relation(src_id, rel, tgt_id, confidence=conf, **extra)
    for axiom in data.get("axioms", []):
        graph.add_axiom(axiom)
    for dp in data.get("data_properties", []):
        entity = dp.get("entity", "")
        attr = dp.get("attribute", "")
        val = dp.get("value", "")
        dtype = dp.get("datatype", "string")
        src_docs = dp.get("source_documents")
        if isinstance(src_docs, list):
            graph.add_data_property(entity, attr, val, dtype, source_documents=src_docs)
        else:
            graph.add_data_property(entity, attr, val, dtype)
    return graph
