"""Matplotlib-based PNG graph visualization."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

_RELATION_COLORS: dict[str, str] = {
    "subClassOf": "#ec4899",
    "type": "#38bdf8",
    "part_of": "#38bdf8",
    "contains": "#a78bfa",
    "depends_on": "#f59e0b",
}
_DEFAULT_EDGE_COLOR = "#6b7280"


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
        nx.draw_networkx_nodes(
            g, pos, nodelist=class_nodes, node_color="#ec4899",
            node_shape="s", node_size=600, ax=ax, alpha=0.9
        )
    if instance_nodes:
        nx.draw_networkx_nodes(
            g, pos, nodelist=instance_nodes, node_color="#38bdf8",
            node_shape="o", node_size=400, ax=ax, alpha=0.9
        )
    if other_nodes:
        nx.draw_networkx_nodes(
            g, pos, nodelist=other_nodes, node_color="#bdc3c7",
            node_shape="o", node_size=300, ax=ax, alpha=0.7
        )

    nx.draw_networkx_labels(g, pos, font_size=7, ax=ax)

    edge_colors = [
        _RELATION_COLORS.get(d.get("relation", ""), _DEFAULT_EDGE_COLOR)
        for _, _, d in g.edges(data=True)
    ]
    nx.draw_networkx_edges(
        g, pos, edge_color=edge_colors, arrows=True, arrowsize=12,
        ax=ax, alpha=0.6, connectionstyle="arc3,rad=0.1"
    )

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
