/**
 * Ontology Graph Viewer - Style engine (node/edge styling)
 * Priority stack: nhopResult drives highlighting atomically with nodes and edges
 */

import { withAlpha, getClusterColor } from "./utils.js";
import { getState } from "./state.js";
import { shouldHideEdge } from "./filters.js";

export function computeNodeStyle(n, stateSnapshot, context) {
  const { nodeDefaults, nodeClusterMap, C } = context;
  const meta = nodeDefaults[n.id] || {};
  const accent = meta.accent || C.accent;
  if (n.hidden) return { id: n.id };

  const { nhopResult, highlightMode } = stateSnapshot;
  const inNeighbourhood = nhopResult?.nodeIds?.has(n.id) ?? false;
  const isFocused = stateSnapshot.focusedNodeId === n.id;
  const isSelected = stateSnapshot.selectedNodeId === n.id;
  const isHover = stateSnapshot.hoveredNodeId === n.id;
  const isDimmed = highlightMode !== "none" && !inNeighbourhood && !isFocused && !isSelected;

  if (isFocused) {
    return {
      id: n.id,
      opacity: 1,
      borderWidth: 2.8,
      color: {
        background: C.bgCardHover,
        border: accent,
        highlight: { background: C.bgCardHover, border: accent },
        hover: { background: C.bgCardHover, border: accent },
      },
      font: { color: C.textPrimary, size: 14, face: "Space Grotesk" },
      shadow: { enabled: true, color: withAlpha(accent, 0.8), size: 22, x: 0, y: 0 },
    };
  }
  if (inNeighbourhood) {
    return {
      id: n.id,
      opacity: 1,
      borderWidth: 2.0,
      color: {
        background: C.bgCard,
        border: accent,
        highlight: { background: C.bgCardHover, border: accent },
        hover: { background: C.bgCardHover, border: accent },
      },
      font: { color: C.textPrimary, size: 13, face: "Space Grotesk" },
      shadow: { enabled: true, color: withAlpha(accent, 0.35), size: 10, x: 0, y: 0 },
    };
  }
  if (isSelected) {
    return {
      id: n.id,
      opacity: 1,
      borderWidth: 2.4,
      color: {
        background: C.bgCardHover,
        border: accent,
        highlight: { background: C.bgCardHover, border: accent },
        hover: { background: C.bgCardHover, border: accent },
      },
      font: { color: C.textPrimary, size: 13, face: "Space Grotesk" },
      shadow: { enabled: true, color: withAlpha(accent, 0.65), size: 12, x: 0, y: 0 },
    };
  }
  if (isDimmed) {
    return { id: n.id, opacity: 0.12 };
  }

  const clusterId = n.cluster != null ? n.cluster : nodeClusterMap[n.id];
  const borderColor =
    isHover ? accent : (clusterId != null && clusterId >= 0 ? getClusterColor(clusterId, C) : C.border);
  return {
    id: n.id,
    borderWidth: isHover ? 2.4 : 1.2,
    color: {
      background: isHover ? C.bgCardHover : C.bgCard,
      border: borderColor,
      highlight: { background: C.bgCardHover, border: accent },
      hover: { background: C.bgCardHover, border: accent },
    },
    font: { color: C.textPrimary, size: 13, face: "Space Grotesk" },
    shadow: false,
  };
}

export function computeEdgeStyle(e, stateSnapshot, context) {
  const {
    edgeDefaults,
    C,
    getRelationLabel,
    edgeLabelsOnHoverOnly,
  } = context;
  const def = edgeDefaults[e.id] || {};
  const base = def.color || C.pending;
  const baseDashes = def.dashes || false;
  const { nhopResult, highlightMode } = stateSnapshot;
  const inNeighbourhood = nhopResult?.edgeIds?.has(e.id) ?? false;
  const hidden = !inNeighbourhood && shouldHideEdge(e, stateSnapshot, context);
  if (hidden) return { id: e.id, hidden: true };
  const isDimmed = highlightMode !== "none" && !inNeighbourhood;

  let edgeLabel = getRelationLabel(e);
  if (edgeLabelsOnHoverOnly) {
    const showOnHover = stateSnapshot.hoveredEdgeId === e.id;
    const showOnSelect = inNeighbourhood;
    edgeLabel = (showOnHover || showOnSelect) ? (e.relation || e.label || "related_to") : "";
  }

  if (inNeighbourhood) {
    const width = (e.width || 1.8) * 1.5;
    const dashes = e.inferred ? [6, 4] : baseDashes;
    return {
      id: e.id,
      label: edgeLabel,
      color: { color: base, opacity: 1 },
      width,
      dashes,
      font: { color: C.textPrimary, background: C.bgCard, face: "JetBrains Mono", size: 10, strokeWidth: 0 },
      isDimmed: false,
    };
  }
  if (isDimmed) {
    return {
      id: e.id,
      label: edgeLabel,
      color: { color: base, opacity: 0.08 },
      width: 0.5,
      dashes: [3, 6],
      font: { color: C.border, background: C.bgBody, face: "JetBrains Mono", size: 10, strokeWidth: 0 },
      isDimmed: true,
    };
  }
  return {
    id: e.id,
    label: edgeLabel,
    color: { color: base, opacity: 0.88 },
    width: 1.8,
    dashes: baseDashes,
    font: { color: C.textMuted, background: C.bgSidebar, face: "JetBrains Mono", size: 10, strokeWidth: 0 },
    isDimmed: false,
  };
}

export function createApplyStyles(nodes, edges, context) {
  let applyStylesRaf = null;
  return function applyStyles() {
    if (applyStylesRaf) return;
    applyStylesRaf = requestAnimationFrame(() => {
      applyStylesRaf = null;
      const stateSnapshot = getState();
      const allNodes = nodes.get();
      const allEdges = edges.get();
      const nodeMap = {};
      allNodes.forEach((n) => { nodeMap[n.id] = n; });
      const edgeContext = { ...context, nodeMap };
      const nodeUpdates = [];
      const edgeUpdates = [];
      for (let i = 0; i < allNodes.length; i++) {
        const u = computeNodeStyle(allNodes[i], stateSnapshot, context);
        if (Object.keys(u).length > 1) nodeUpdates.push(u);
      }
      for (let j = 0; j < allEdges.length; j++) {
        const ev = computeEdgeStyle(allEdges[j], stateSnapshot, edgeContext);
        edgeUpdates.push(ev);
      }
      if (nodeUpdates.length) nodes.update(nodeUpdates);
      if (edgeUpdates.length) edges.update(edgeUpdates);
    });
  };
}
