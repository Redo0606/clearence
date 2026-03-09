/**
 * Ontology Graph Viewer - Spotlight mode (focus on node neighborhood)
 */

import { state, setState } from "./state.js";
import { debugLog } from "./utils.js";

const SPOTLIGHT_BLUR_ENABLED = true;

export function enterSpotlight(network, nodeId, callbacks) {
  const { container, spotlightBg, DEBUG, applyStyles, applyLabelVisibility, computeAndCacheNhop } =
    callbacks;

  if (!state.focusedNodeId && SPOTLIGHT_BLUR_ENABLED) {
    setState({ savedContainerBackground: container.style.background || "" });
    const visCanvas = container.querySelector("canvas");
    if (visCanvas) {
      try {
        const url = visCanvas.toDataURL();
        if (url) spotlightBg.style.backgroundImage = "url(" + url + ")";
      } catch (err) {
        if (DEBUG) debugLog(DEBUG, "Spotlight bg snapshot skipped", err);
      }
    }
    spotlightBg.classList.add("active");
    container.style.background = "transparent";
  }

  const depth = state.selectedDepth >= 999 ? 10 : state.selectedDepth;
  computeAndCacheNhop(nodeId, depth);
  setState({
    focusedNodeId: nodeId,
    selectedNodeId: nodeId,
    highlightMode: "spotlight",
  });
  applyStyles();

  const relatedArr = Array.from(state.nhopResult?.nodeIds ?? []);
  if (relatedArr.length > 0) {
    network.fit({ nodes: relatedArr, animation: { duration: 380, easingFunction: "easeInOutCubic" } });
  } else {
    network.focus(nodeId, { scale: 1.2, animation: { duration: 380, easingFunction: "easeInOutCubic" } });
  }
  applyLabelVisibility(nodeId);
}

export function exitSpotlight(network, callbacks) {
  const { container, spotlightBg, applyStyles } = callbacks;

  if (!state.focusedNodeId) return;
  setState({
    focusedNodeId: null,
    selectedNodeId: null,
    highlightMode: "none",
    nhopResult: null,
  });
  spotlightBg.classList.remove("active");
  container.style.background = state.savedContainerBackground || "";
  applyStyles();
  network.fit({ animation: { duration: 380, easingFunction: "easeInOutCubic" } });
}

export function updateSpotlightDepth(depth, callbacks) {
  const { computeAndCacheNhop, applyStyles } = callbacks;
  const nodeId = state.focusedNodeId ?? state.selectedNodeId;
  if (!nodeId) return;
  computeAndCacheNhop(nodeId, depth);
  applyStyles();
}
