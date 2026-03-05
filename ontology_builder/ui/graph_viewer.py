"""Graph visualization: Matplotlib PNG and interactive vis.js HTML.

Differentiates classes (rectangles/blue) from instances (circles/green),
colors edges by relation type.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

_RELATION_COLORS: dict[str, str] = {
    "subClassOf": "#e74c3c",
    "type": "#2ecc71",
    "part_of": "#3498db",
    "contains": "#9b59b6",
    "depends_on": "#f39c12",
}
_DEFAULT_EDGE_COLOR = "#95a5a6"


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

    pos = nx.spring_layout(g, seed=42, k=2.0)

    class_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "class"]
    instance_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "instance"]
    other_nodes = [n for n in g.nodes() if n not in class_nodes and n not in instance_nodes]

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    if class_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=class_nodes, node_color="#3498db",
                               node_shape="s", node_size=600, ax=ax, alpha=0.9)
    if instance_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=instance_nodes, node_color="#2ecc71",
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
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#3498db", markersize=10, label="Class"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ecc71", markersize=10, label="Instance"),
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


def generate_visjs_html(graph: "OntologyGraph") -> str:
    """Generate standalone HTML page with interactive vis.js graph viewer."""
    g = graph.get_graph()

    vis_nodes: list[dict[str, Any]] = []
    for node in g.nodes():
        data = g.nodes[node]
        kind = data.get("kind", "class")
        label = node
        desc = data.get("description", "")
        color = "#3498db" if kind == "class" else "#2ecc71"
        shape = "box" if kind == "class" else "ellipse"
        title = f"<b>{node}</b><br>Kind: {kind}<br>{desc}" if desc else f"<b>{node}</b><br>Kind: {kind}"
        vis_nodes.append({
            "id": node,
            "label": label,
            "color": color,
            "shape": shape,
            "title": title,
        })

    vis_edges: list[dict[str, Any]] = []
    for u, v, data in g.edges(data=True):
        rel = data.get("relation", "related_to")
        color = _RELATION_COLORS.get(rel, _DEFAULT_EDGE_COLOR)
        vis_edges.append({
            "from": u,
            "to": v,
            "label": rel,
            "arrows": "to",
            "color": {"color": color},
            "font": {"size": 10, "align": "middle"},
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)
    stats = graph.export().get("stats", {})
    stats_html = (
        f"Classes: {stats.get('classes', 0)} | "
        f"Instances: {stats.get('instances', 0)} | "
        f"Edges: {stats.get('edges', 0)} | "
        f"Axioms: {stats.get('axioms', 0)}"
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ontology Graph Viewer</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif; background: #1a1a2e; color: #eee; }}
    #header {{ padding: 16px 24px; background: #16213e; display: flex; justify-content: space-between; align-items: center; }}
    #header h1 {{ font-size: 20px; font-weight: 600; }}
    #stats {{ font-size: 13px; opacity: 0.7; }}
    #legend {{ display: flex; gap: 16px; font-size: 12px; }}
    .legend-item {{ display: flex; align-items: center; gap: 4px; }}
    .legend-dot {{ width: 12px; height: 12px; border-radius: 2px; }}
    #graph {{ width: 100vw; height: calc(100vh - 56px); }}
  </style>
</head>
<body>
  <div id="header">
    <div>
      <h1>Ontology Graph Viewer</h1>
      <div id="stats">{stats_html}</div>
    </div>
    <div id="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div> Class</div>
      <div class="legend-item"><div class="legend-dot" style="background:#2ecc71;border-radius:50%"></div> Instance</div>
    </div>
  </div>
  <div id="graph"></div>
  <script>
    var nodes = new vis.DataSet({nodes_json});
    var edges = new vis.DataSet({edges_json});
    var container = document.getElementById("graph");
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
      physics: {{ stabilization: {{ iterations: 200 }}, barnesHut: {{ gravitationalConstant: -4000 }} }},
      interaction: {{ hover: true, tooltipDelay: 100, navigationButtons: true }},
      nodes: {{ font: {{ color: "#fff", size: 13 }} }},
      edges: {{ smooth: {{ type: "curvedCW", roundness: 0.15 }} }}
    }};
    new vis.Network(container, data, options);
  </script>
</body>
</html>"""
