"""Matplotlib-based graph visualization. Renders ontology as node-edge diagram."""

import io
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph


def visualize(graph: "OntologyGraph", save_path: str | None = None) -> io.BytesIO | None:
    """Draw ontology graph with node and edge labels.

    Args:
        graph: OntologyGraph to visualize.
        save_path: If set, save PNG to file and return None. Else return BytesIO.

    Returns:
        BytesIO with PNG bytes, or None if save_path was used.
    """
    g = graph.get_graph()
    if g.number_of_nodes() == 0:
        if save_path:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Empty graph", ha="center", va="center")
            fig.savefig(save_path)
            plt.close(fig)
        return None

    pos = nx.spring_layout(g, seed=42)
    nx.draw(g, pos, with_labels=True, node_color="lightblue", font_size=8)
    edge_labels = nx.get_edge_attributes(g, "relation")
    nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels, font_size=6)

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
        plt.close()
        return None

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf
