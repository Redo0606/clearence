/**
 * Ontology Graph Viewer - Central state manager
 */

export const state = {
  selectedNodeId: null,
  focusedNodeId: null,
  hoveredNodeId: null,
  hoveredEdgeId: null,
  edgeFilter: "all",
  viewMode: "full",
  selectedDepth: 1,
  zoomScale: 1,
  showEdgeLabels: true,
  showAllHubEdges: false,
  layoutMode: "galaxy",
  simulationFrozen: false,
  savedContainerBackground: "",
  /** { nodeIds: Set, edgeIds: Set } | null — current neighbourhood for highlighting */
  nhopResult: null,
  /** "none" | "selection" | "spotlight" */
  highlightMode: "none",
  /** Cache keyed by `${nodeId}:${depth}` */
  nhopCache: new Map(),
  /** When true, clicking canvas does not close detail panel */
  panelPinned: false,
  /** Selection history for ←/→ navigation (max 20) */
  selectionHistory: [],
};

export const nhopCache = state.nhopCache;

export function getState() {
  return {
    selectedNodeId: state.selectedNodeId,
    focusedNodeId: state.focusedNodeId,
    hoveredNodeId: state.hoveredNodeId,
    hoveredEdgeId: state.hoveredEdgeId,
    selectedDepth: state.selectedDepth,
    edgeFilter: state.edgeFilter,
    viewMode: state.viewMode,
    zoomScale: state.zoomScale,
    showAllHubEdges: state.showAllHubEdges,
    nhopResult: state.nhopResult,
    highlightMode: state.highlightMode,
  };
}

export function setState(updates) {
  Object.assign(state, updates);
}

export function clearNhopCache() {
  state.nhopCache.clear();
}
