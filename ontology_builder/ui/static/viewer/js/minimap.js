/**
 * Ontology Graph Viewer - Minimap for large graphs
 */

export function createMinimap(minimapEl, network, nodes, edges, C) {
  const vis = window.vis;
  if (!minimapEl || !network || typeof vis === "undefined") return null;
  if (minimapEl.querySelector("canvas")) return null;

  minimapEl.classList.add("visible");
  minimapEl.style.pointerEvents = "auto";

  const mmNodes = new vis.DataSet(
    nodes.get().map((n) => ({
      id: n.id,
      label: "",
      shape: "dot",
      size: 4,
      color: n.accent || C.accent,
    }))
  );
  const mmEdges = new vis.DataSet(
    edges.get().filter((e) => !e.hidden).map((e) => ({ from: e.from, to: e.to, width: 0.5 }))
  );

  const mmNet = new vis.Network(minimapEl, { nodes: mmNodes, edges: mmEdges }, {
    physics: { enabled: false },
    interaction: { dragNodes: false, zoomView: true, dragView: true },
    nodes: { font: { size: 0 } },
    edges: { smooth: false },
  });

  const pos = network.getPositions();
  const updates = Object.entries(pos).map(([id, p]) => ({ id, x: p.x, y: p.y }));
  if (updates.length) mmNodes.update(updates);
  mmNet.fit();
  return mmNet;
}
