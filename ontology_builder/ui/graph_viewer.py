"""Graph visualization: Matplotlib PNG and interactive vis.js HTML.

Differentiates classes (rectangles/blue) from instances (circles/green),
colors edges by relation type. Uses normalized graph model for stable layout.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

    NODE_WIDTH = 140
    NODE_HEIGHT = 40
    vis_nodes: list[dict[str, Any]] = []
    for n in ng.nodes:
        if n.id == "__root__":
            continue
        kind = n.type
        accent = "#b81365" if kind == "class" else "#b1ddf1" if kind == "instance" else "#a08898"
        vis_nodes.append({
            "id": n.id,
            "baseLabel": n.label,
            "label": n.label,
            "kind": kind,
            "accent": accent,
            "description": n.metadata.get("description", ""),
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
        })

    vis_edges: list[dict[str, Any]] = []
    edge_attrs: dict[str, dict[str, Any]] = {}
    g_raw = graph.get_graph()
    for e in ng.edges:
        if e.source == "__root__" or e.target == "__root__":
            continue
        eid = _edge_id(e.source, e.target, e.relation)
        style = _EDGE_STYLES.get(e.relation, {"width": 1.5, "dashes": False, "color": _DEFAULT_EDGE_COLOR})
        color = style.get("color", _RELATION_COLORS.get(e.relation, _DEFAULT_EDGE_COLOR))
        vis_edges.append({
            "id": eid,
            "from": e.source,
            "to": e.target,
            "label": e.relation,
            "relation": e.relation,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": color, "opacity": 0.96, "highlight": color, "hover": color},
            "width": style.get("width", 1.5) if not e.inferred else 1.2,
            "dashes": style.get("dashes", False),
            "smooth": {"type": "cubicBezier"},
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
    }


def _load_template():
    """Load Jinja2 template from ui/templates/graph_viewer.html.j2."""
    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    return env.get_template("graph_viewer.html.j2")


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
        pre_select_node_json=json.dumps(pre_select_node),
        depth_json=json.dumps(depth),
        debug_json=json.dumps(debug),
        theme=theme,
        css_root=css_root,
    )

