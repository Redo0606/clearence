"""NetworkX-based ontology graph. Wraps DiGraph for entities and relations."""

import networkx as nx
from typing import Any


class OntologyGraph:
    """NetworkX DiGraph wrapper for ontology entities and relations."""

    def __init__(self) -> None:
        """Create an empty ontology graph."""
        self.graph = nx.DiGraph()

    def add_entity(self, name: str, etype: str) -> None:
        """Add an entity node with type attribute."""
        self.graph.add_node(name, type=etype)

    def add_relation(self, source: str, relation: str, target: str) -> None:
        """Add a directed relation edge from source to target."""
        self.graph.add_edge(source, target, relation=relation)

    def get_graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX DiGraph."""
        return self.graph

    def export(self) -> dict[str, Any]:
        """Export graph as node-link JSON (nodes, links, directed)."""
        return nx.node_link_data(self.graph)
