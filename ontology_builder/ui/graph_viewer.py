"""Graph visualization: Matplotlib PNG and interactive vis.js HTML.

Differentiates classes (rectangles/blue) from instances (circles/green),
colors edges by relation type. Uses normalized graph model for stable layout.
"""

from __future__ import annotations

import hashlib
import math
import io
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from jinja2 import Environment, FileSystemLoader

from ontology_builder.ui.graph_models import normalize_graph
from ontology_builder.ui.theme import get_css_root_block, get_theme

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

# Theme-aligned defaults (actual colours injected via CSS vars at runtime)
_RELATION_COLORS: dict[str, str] = {
    "subClassOf": "#b81365",
    "type": "#b1ddf1",
    "instanceOf": "#b1ddf1",
    "part_of": "#b1ddf1",
    "contains": "#f8c630",
    "depends_on": "#fad54e",
}
_DEFAULT_EDGE_COLOR = "#6b7fa8"

# Relation-specific spring lengths for semantic layout (Section 5)
RELATION_SPRING_LENGTH: dict[str, int] = {
    "subClassOf": 260,
    "instanceOf": 180,
    "type": 180,
    "depends_on": 320,
    "contains": 220,
    "part_of": 240,
}

HUB_DEGREE_THRESHOLD = 80  # Nodes with degree > this are hubs (Phase 2 Section 3)
HUB_EDGE_CAP = 25  # Max edges shown for hubs until "show all"

_EDGE_STYLES: dict[str, dict[str, Any]] = {
    "subClassOf": {"width": 2.2, "dashes": False, "color": "#b81365"},
    "type": {"width": 1.6, "dashes": [6, 4], "color": "#b1ddf1"},
    "instanceOf": {"width": 1.6, "dashes": [6, 4], "color": "#b1ddf1"},
    "part_of": {"width": 1.5, "dashes": [4, 3], "color": "#b1ddf1"},
    "contains": {"width": 1.5, "dashes": False, "color": "#f8c630"},
    "depends_on": {"width": 1.5, "dashes": [3, 2], "color": "#fad54e"},
}


def _edge_id(u: str, v: str, rel: str) -> str:
    """Stable id for an edge so Python edge_attrs and JS use the same key."""
    return hashlib.md5(f"{u}\x00{v}\x00{rel}".encode()).hexdigest()[:12]


def _to_json_safe(obj: Any) -> Any:
    """Convert numpy and other non-JSON-serializable types to native Python for json.dumps."""
    if obj is None:
        return None
    if hasattr(obj, "item"):  # numpy scalar (float32, int64, etc.)
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    return obj


def _build_vis_data(graph: "OntologyGraph") -> dict[str, Any]:
    """Build vis.js nodes/edges and metadata; edge_attrs keyed by same id as vis edges."""
    ng = normalize_graph(graph)
    logger.info(
        "Graph normalized: %d nodes, %d edges, roots=%s, cycles=%s, disconnected=%d",
        len(ng.nodes),
        len(ng.edges),
        ng.roots[:5] if len(ng.roots) > 5 else ng.roots,
        ng.has_cycles,
        ng.disconnected_count,
    )

    NODE_WIDTH = 160
    NODE_HEIGHT = 50
    g_raw = graph.get_graph()
    degree_map = dict(g_raw.degree())
    vis_nodes: list[dict[str, Any]] = []
    for n in ng.nodes:
        if n.id == "__root__":
            continue
        kind = n.type
        accent = "#b81365" if kind == "class" else "#b1ddf1" if kind == "instance" else "#a08898"
        degree = degree_map.get(n.id, 1)
        is_hub = degree > HUB_DEGREE_THRESHOLD
        # Section 7: size = 20 + log(degree+1)*14, cap at 90
        node_size = min(90, 20 + math.log(degree + 1) * 14)
        vis_nodes.append({
            "id": n.id,
            "baseLabel": n.label,
            "label": n.label,
            "kind": kind,
            "accent": accent,
            "description": n.metadata.get("description", ""),
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "degree": degree,
            "isHub": is_hub,
            "mass": max(1.5, min(6, degree * 0.6)),
            "size": node_size,
        })

    hub_ids = {nid for nid, d in degree_map.items() if d > HUB_DEGREE_THRESHOLD}
    hub_out_rank: dict[tuple[str, str, str], int] = {}
    hub_in_rank: dict[tuple[str, str, str], int] = {}
    for nid in hub_ids:
        out_edges = [(e.source, e.target, e.relation) for e in ng.edges if e.source == nid and e.source != "__root__" and e.target != "__root__"]
        for i, key in enumerate(out_edges):
            hub_out_rank[key] = i
        in_edges = [(e.source, e.target, e.relation) for e in ng.edges if e.target == nid and e.source != "__root__" and e.target != "__root__"]
        for i, key in enumerate(in_edges):
            hub_in_rank[key] = i

    vis_edges: list[dict[str, Any]] = []
    edge_attrs: dict[str, dict[str, Any]] = {}
    for e in ng.edges:
        if e.source == "__root__" or e.target == "__root__":
            continue
        eid = _edge_id(e.source, e.target, e.relation)
        style = _EDGE_STYLES.get(e.relation, {"width": 1.5, "dashes": False, "color": _DEFAULT_EDGE_COLOR})
        color = style.get("color", _RELATION_COLORS.get(e.relation, _DEFAULT_EDGE_COLOR))
        # Edge length by relation type (Section 5); opacity by correctness (Section 12)
        edge_len = RELATION_SPRING_LENGTH.get(e.relation, 240)
        correctness = None
        for _u, _v, data in g_raw.edges(e.source, e.target, data=True):
            if data.get("relation") == e.relation:
                correctness = data.get("correctness_score")
                break
        opacity = 0.35 + (correctness * 0.6) if correctness is not None else 0.96
        edge_key = (e.source, e.target, e.relation)
        out_rank = hub_out_rank.get(edge_key, -1)
        in_rank = hub_in_rank.get(edge_key, -1)
        vis_edges.append({
            "id": eid,
            "from": e.source,
            "to": e.target,
            "label": e.relation,
            "hubOutRank": out_rank if out_rank >= 0 else None,
            "hubInRank": in_rank if in_rank >= 0 else None,
            "relation": e.relation,
            "length": edge_len,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": color, "opacity": opacity, "highlight": color, "hover": color},
            "width": style.get("width", 1.5) if not e.inferred else 1.2,
            "dashes": style.get("dashes", False),
            "curveOffset": (int(hashlib.md5(e.relation.encode()).hexdigest()[:8], 16) % 100) / 100.0 * 0.3,
            "font": {
                "size": 10,
                "align": "middle",
                "face": "JetBrains Mono",
                "color": "#f7f7f9",
                "background": "#150c0f",
                "strokeWidth": 0,
            },
        })

    for u, v, data in g_raw.edges(data=True):
        rel = data.get("relation", "related_to")
        key = _edge_id(u, v, rel)
        prov = data.get("provenance") or {}
        edge_attrs[key] = {
            "correctness_score": data.get("correctness_score"),
            "cross_chunk_votes": data.get("cross_chunk_votes"),
            "derivation_path_length": data.get("derivation_path_length"),
            "provenance_origin": prov.get("origin", "extraction"),
            "provenance_rule": prov.get("rule", ""),
        }

    node_attrs: dict[str, dict[str, Any]] = {}
    for nid in g_raw.nodes():
        d = g_raw.nodes[nid]
        node_attrs[nid] = {
            "kind": d.get("kind", "class"),
            "description": d.get("description", ""),
            "source_documents": d.get("source_documents", []),
        }

    sub_class_count = sum(1 for e in vis_edges if e.get("relation") == "subClassOf")
    sub_class_ratio = sub_class_count / len(vis_edges) if vis_edges else 0

    stats = graph.export().get("stats", {})
    rel_count = stats.get("relations")
    if rel_count is None:
        rel_count = stats.get("edges")
    if rel_count is None:
        rel_count = len(vis_edges)
    cluster_info = f"Clusters: {len(ng.clusters)}" if ng.clusters else ""
    isolated_info = f"Isolated: {len(ng.isolated)}" if ng.isolated else ""
    stats_html = (
        f"Classes: {stats.get('classes', 0)} | "
        f"Instances: {stats.get('instances', 0)} | "
        f"Relations: {rel_count} | "
        f"Axioms: {stats.get('axioms', 0)}"
        + (f" | {cluster_info}" if cluster_info else "")
        + (f" | {isolated_info}" if isolated_info else "")
    )

    return {
        "nodes": vis_nodes,
        "edges": vis_edges,
        "edge_attrs": edge_attrs,
        "node_attrs": node_attrs,
        "relations": sorted({e["relation"] for e in vis_edges}),
        "hierarchy": {n.id: ng.hierarchy_levels.get(n.id, 999) for n in ng.nodes if n.id != "__root__"},
        "clusters": [list(c) for c in ng.clusters],
        "isolated": list(ng.isolated),
        "has_cycles": ng.has_cycles,
        "stats_html": stats_html,
        "sub_class_ratio": sub_class_ratio,
        "hub_ids": list(hub_ids),
    }


def _load_template():
    """Load Jinja2 template from ui/templates/graph_viewer.html.j2."""
    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    return env.get_template("graph_viewer.html.j2")


def _persist_vis_data(path: Path, graph: "OntologyGraph") -> None:
    """Persist pre-computed vis data to .vis.json for fast view loads."""
    try:
        vis_data = _build_vis_data(graph)
        # Ensure JSON-serializable (numpy types from graph edge data cause orjson to fail)
        vis_data = _to_json_safe(vis_data)
        out = {
            "nodes": vis_data["nodes"],
            "edges": vis_data["edges"],
            "edge_attrs": vis_data["edge_attrs"],
            "node_attrs": vis_data["node_attrs"],
            "relations": vis_data["relations"],
            "hierarchy": vis_data["hierarchy"],
            "clusters": vis_data["clusters"],
            "isolated": vis_data["isolated"],
            "has_cycles": vis_data["has_cycles"],
            "stats_html": vis_data["stats_html"],
            "sub_class_ratio": vis_data.get("sub_class_ratio", 0),
            "hub_ids": vis_data.get("hub_ids", []),
        }
        vis_path = path.parent / (path.stem + ".vis.json")
        vis_path.write_bytes(orjson.dumps(out))
        logger.debug("[GraphViewer] Persisted vis data to %s", vis_path.name)
    except Exception as e:
        logger.debug("[GraphViewer] Persist vis data failed: %s", e)


def render_vis_from_file(
    vis_path: Path,
    pre_select_node: str | None = None,
    depth: int = 1,
    debug: bool = False,
) -> str:
    """Render graph viewer HTML from pre-computed .vis.json (no graph load)."""
    vis_data = orjson.loads(vis_path.read_bytes())
    theme = get_theme()
    css_root = get_css_root_block()
    return _load_template().render(
        nodes_json=json.dumps(vis_data["nodes"]),
        edges_json=json.dumps(vis_data["edges"]),
        edge_attrs_json=json.dumps(vis_data["edge_attrs"]),
        node_attrs_json=json.dumps(vis_data["node_attrs"]),
        relations_json=json.dumps(vis_data["relations"]),
        hierarchy_json=json.dumps(vis_data["hierarchy"]),
        clusters_json=json.dumps(vis_data["clusters"]),
        isolated_json=json.dumps(vis_data["isolated"]),
        has_cycles_json=json.dumps(vis_data["has_cycles"]),
        stats_html=vis_data["stats_html"],
        sub_class_ratio_json=json.dumps(vis_data.get("sub_class_ratio", 0)),
        hub_ids_json=json.dumps(vis_data.get("hub_ids", [])),
        pre_select_node_json=json.dumps(pre_select_node),
        depth_json=json.dumps(depth),
        debug_json=json.dumps(debug),
        theme=theme,
        css_root=css_root,
    )


def visualize(graph: "OntologyGraph", save_path: str | None = None) -> io.BytesIO | None:
    """Draw ontology graph as PNG with class/instance differentiation."""
    g = graph.get_graph()
    if g.number_of_nodes() == 0:
        if save_path:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Empty graph", ha="center", va="center")
            fig.savefig(save_path)
            plt.close(fig)
        return None

    pos = nx.spring_layout(g, seed=42, k=3.5)

    class_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "class"]
    instance_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "instance"]
    other_nodes = [n for n in g.nodes() if n not in class_nodes and n not in instance_nodes]

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    if class_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=class_nodes, node_color="#ec4899",
                               node_shape="s", node_size=600, ax=ax, alpha=0.9)
    if instance_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=instance_nodes, node_color="#38bdf8",
                               node_shape="o", node_size=400, ax=ax, alpha=0.9)
    if other_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=other_nodes, node_color="#bdc3c7",
                               node_shape="o", node_size=300, ax=ax, alpha=0.7)

    nx.draw_networkx_labels(g, pos, font_size=7, ax=ax)

    edge_colors = [_RELATION_COLORS.get(d.get("relation", ""), _DEFAULT_EDGE_COLOR)
                   for _, _, d in g.edges(data=True)]
    nx.draw_networkx_edges(g, pos, edge_color=edge_colors, arrows=True, arrowsize=12,
                           ax=ax, alpha=0.6, connectionstyle="arc3,rad=0.1")

    edge_labels = nx.get_edge_attributes(g, "relation")
    nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels, font_size=5, ax=ax)

    ax.set_title("Ontology Graph", fontsize=14, fontweight="bold")
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#ec4899", markersize=10, label="Class"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#38bdf8", markersize=10, label="Instance"),
        ],
        loc="upper left",
    )
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        return None

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_visjs_html(
    graph: "OntologyGraph",
    pre_select_node: str | None = None,
    depth: int = 1,
    debug: bool = False,
) -> str:
    """Generate standalone HTML page with interactive vis.js graph viewer."""
    vis_data = _build_vis_data(graph)
    # Ensure JSON-serializable (numpy types from graph edge data cause 500 on json.dumps)
    vis_data = _to_json_safe(vis_data)
    theme = get_theme()
    css_root = get_css_root_block()
    return _load_template().render(
        nodes_json=json.dumps(vis_data["nodes"]),
        edges_json=json.dumps(vis_data["edges"]),
        edge_attrs_json=json.dumps(vis_data["edge_attrs"]),
        node_attrs_json=json.dumps(vis_data["node_attrs"]),
        relations_json=json.dumps(vis_data["relations"]),
        hierarchy_json=json.dumps(vis_data["hierarchy"]),
        clusters_json=json.dumps(vis_data["clusters"]),
        isolated_json=json.dumps(vis_data["isolated"]),
        has_cycles_json=json.dumps(vis_data["has_cycles"]),
        stats_html=vis_data["stats_html"],
        sub_class_ratio_json=json.dumps(vis_data.get("sub_class_ratio", 0)),
        hub_ids_json=json.dumps(vis_data.get("hub_ids", [])),
        pre_select_node_json=json.dumps(pre_select_node),
        depth_json=json.dumps(depth),
        debug_json=json.dumps(debug),
        theme=theme,
        css_root=css_root,
    )

