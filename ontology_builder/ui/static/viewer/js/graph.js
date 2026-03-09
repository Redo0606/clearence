/**
 * Ontology Graph Viewer - vis.Network creation and options
 */

export function createGraph(container, nodes, edges, options) {
  const vis = window.vis;
  if (typeof vis === "undefined" || !vis?.DataSet || !vis?.Network) {
    throw new Error("vis-network library unavailable");
  }
  const data = { nodes, edges };
  const network = new vis.Network(container, data, options);
  return network;
}

export function buildGraphOptions(C) {
  return {
    autoResize: true,
    layout: { improvedLayout: false, hierarchical: { enabled: false } },
    physics: { enabled: false },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      navigationButtons: false,
      keyboard: true,
      dragNodes: true,
      zoomView: true,
      dragView: true,
    },
    nodes: {
      shape: "box",
      shapeProperties: { borderRadius: 8 },
      margin: 12,
      widthConstraint: { minimum: 160, maximum: 280 },
      font: { color: C.textPrimary, size: 13, face: "Space Grotesk" },
      borderWidth: 1.2,
      borderWidthSelected: 2.2,
      color: {
        background: C.bgCard,
        border: C.border,
        highlight: { background: C.bgCardHover, border: C.accent },
        hover: { background: C.bgCardHover, border: C.accent },
      },
    },
    edges: {
      smooth: { enabled: true, type: "cubicBezier", forceDirection: "vertical", roundness: 0.6 },
      width: 1.8,
      hoverWidth: 2,
      selectionWidth: 2,
      font: { size: 10, align: "middle" },
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      labelHighlightBold: true,
      color: { inherit: false },
    },
    configure: false,
  };
}
