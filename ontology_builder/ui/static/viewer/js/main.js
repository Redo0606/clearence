/**
 * Ontology Graph Viewer - Main entry point
 * Reads from window.__GRAPH_DATA__ (injected by Jinja template)
 */

import {
  getThemeColors,
  buildNodeClusterMap,
  buildStaticAdjacency,
  adjacencyFromBackend,
  buildNhopNeighbourhood,
  buildAdjacencyMap,
  getClusterColor,
  debugLog,
  showToast,
  CLUSTER_PALETTE,
  HUB_EDGE_CAP,
} from "./utils.js";
import { state, getState, setState, clearNhopCache } from "./state.js";
import { createGraph, buildGraphOptions } from "./graph.js";
import { galaxyLayout, drawHullOverlay } from "./layout.js";
import { createApplyStyles, computeNodeStyle, computeEdgeStyle } from "./styles.js";
import { showTooltip, hideTooltip } from "./tooltip.js";
import {
  buildNodeRelationSummary,
  renderNodeDetail,
  renderEdgeDetail,
} from "./detailPanel.js";
import { enterSpotlight, exitSpotlight } from "./spotlight.js";
import { createMinimap } from "./minimap.js";

(function init() {
try {
  const initError = document.getElementById("viewer-init-error");
  const graphContainer = document.getElementById("graph");

  function showInitError(message) {
    if (initError) {
      initError.textContent = message;
      initError.classList.add("visible");
    }
    if (graphContainer) {
      graphContainer.style.opacity = "1";
      graphContainer.style.transform = "none";
    }
  }

  const vis = window.vis;
  if (typeof vis === "undefined" || !vis?.DataSet || !vis?.Network) {
    showInitError("Graph viewer assets failed to load. Check network access to unpkg.com and refresh the page.");
    return;
  }

  const data = window.__GRAPH_DATA__;
  if (!data || !data.nodes || !data.edges) {
    showInitError("Graph data not loaded.");
    return;
  }

  const nodes = new vis.DataSet(data.nodes);
  const edges = new vis.DataSet(data.edges);
  const container = document.getElementById("graph");
  const tooltip = document.getElementById("node-tooltip");
  const edgeLabelToggle = document.getElementById("edge-label-toggle");
  const fitBtn = document.getElementById("fit-btn");
  const spotlightBg = document.getElementById("spotlight-bg");
  const progressBar = document.getElementById("stabilization-progress-bar");
  const progressWrap = document.getElementById("stabilization-progress");
  const hullCanvas = document.getElementById("hull-overlay");
  const detailPanel = document.getElementById("detail-panel");
  const detailContent = document.getElementById("detail-content");
  const detailPanelClose = document.getElementById("detail-panel-close");
  const depthSlider = document.getElementById("depth-slider");
  const depthBadge = document.getElementById("depth-badge");

  const nodeCount = nodes.get().length;
  const C = getThemeColors();
  const DEBUG = data.debug || false;
  const clusters = data.clusters || [];
  const edgeAttrs = data.edge_attrs || {};
  const nodeAttrs = data.node_attrs || {};
  const hierarchyLevels = data.hierarchy || {};
  const hubIds = new Set(data.hub_ids || []);
  const hasCycles = data.has_cycles || false;
  const preSelectNode = data.pre_select_node || null;
  const initialDepth = data.depth || 1;

  setState({
    selectedDepth: initialDepth,
    showEdgeLabels: nodeCount < 400,
  });

  const nodeDefaults = {};
  const edgeDefaults = {};
  nodes.forEach((n) => {
    nodeDefaults[n.id] = {
      accent: n.accent || C.accent,
      kind: n.kind || "class",
      description: n.description || "",
    };
  });
  edges.forEach((e) => {
    edgeDefaults[e.id] = {
      color: e.color && e.color.color ? e.color.color : C.pending,
      dashes: e.dashes || false,
    };
  });

  const nodeClusterMap = buildNodeClusterMap(nodes.get(), clusters);
  const staticAdjacency =
    adjacencyFromBackend(data.adjacency) || buildStaticAdjacency(edges.get());
  const adjacencyMap =
    data.adjacency && typeof data.adjacency === "object"
      ? new Map(Object.entries(data.adjacency).map(([k, v]) => [k, v || []]))
      : buildAdjacencyMap(edges.get());
  const edgeLabelsOnHoverOnly = nodeCount > 200;

  function getConnectedNodesNHop(nodeId, hops) {
    const key = nodeId + ":" + hops;
    if (state.nhopCache.has(key)) return state.nhopCache.get(key).nodeIds;
    const result = buildNhopNeighbourhood(nodeId, hops, adjacencyMap);
    state.nhopCache.set(key, result);
    return result.nodeIds;
  }

  function getConnectedEdgesForNodes(nodeSet) {
    const edgeSet = new Set();
    edges.get().forEach((e) => {
      if (e.id && (nodeSet.has(e.from) || nodeSet.has(e.to))) edgeSet.add(e.id);
    });
    return edgeSet;
  }

  function computeAndCacheNhop(nodeId, depth) {
    const key = nodeId + ":" + depth;
    if (!state.nhopCache.has(key)) {
      state.nhopCache.set(key, buildNhopNeighbourhood(nodeId, depth, adjacencyMap));
    }
    state.nhopResult = state.nhopCache.get(key);
  }

  function getRelationLabel(edge) {
    if (edgeLabelsOnHoverOnly) return "";
    const rel = edge && (edge.relation || edge.label) ? edge.relation || edge.label : "related_to";
    return state.showEdgeLabels ? rel : "";
  }

  const styleContext = {
    nodeDefaults,
    edgeDefaults,
    nodeClusterMap,
    C,
    getRelationLabel,
    edgeLabelsOnHoverOnly,
    hubIds,
  };

  const applyStyles = createApplyStyles(nodes, edges, styleContext);

  function applyLabelVisibility(focusNodeId, zoomScale) {
    const scale = zoomScale != null ? zoomScale : state.zoomScale;
    const fn = focusNodeId || state.selectedNodeId || state.focusedNodeId;
    const related = state.nhopResult?.nodeIds ?? (fn ? getConnectedNodesNHop(fn, state.selectedDepth >= 999 ? 10 : state.selectedDepth) : null);
    const allNodes = nodes.get();
    const updates = [];
    const showAllWhenZoomedIn = scale >= 0.75;
    const showSomeWhenZoomed = scale >= 0.5;
    for (let i = 0; i < allNodes.length; i++) {
      const n = allNodes[i];
      if (n.hidden) continue;
      const showLabel =
        showAllWhenZoomedIn ||
        n.id === fn ||
        (related && related.has(n.id)) ||
        (showSomeWhenZoomed && n.degree != null && n.degree > 5) ||
        state.hoveredNodeId === n.id;
      updates.push({ id: n.id, label: showLabel ? (n.baseLabel || n.label || n.id) : "" });
    }
    if (updates.length) nodes.update(updates);
  }

  function applyEdgeLabelMode() {
    const allEdges = edges.get();
    const updates = allEdges.map((e) => ({
      id: e.id,
      label: getRelationLabel(e),
    }));
    if (updates.length) edges.update(updates);
    if (edgeLabelToggle) edgeLabelToggle.textContent = "Labels: " + (state.showEdgeLabels ? "ON" : "OFF");
  }

  function doDrawHullOverlay() {
    drawHullOverlay(network, clusters, hullCanvas, C, nodeCount);
  }

  const options = buildGraphOptions(C);
  const network = createGraph(container, nodes, edges, options);

  network.on("dragEnd", () => {
    // Manual layout (galaxy/ELK) – do not re-enable physics; it pulls nodes to center
  });

  network.on("stabilizationProgress", (params) => {
    if (progressBar && progressWrap) {
      const pct = params.total ? (params.iterations / params.total) * 100 : 0;
      progressBar.style.width = pct + "%";
    }
  });

  let hullDrawThrottle = null;
  network.on("afterDrawing", () => {
    if (hullDrawThrottle) clearTimeout(hullDrawThrottle);
    hullDrawThrottle = setTimeout(() => {
      hullDrawThrottle = null;
      doDrawHullOverlay();
    }, 150);
  });

  network.on("zoom", (params) => {
    setState({ zoomScale: params.scale });
    if (params.scale < 0.45) {
      const allNodes = nodes.get();
      nodes.update(allNodes.map((n) => ({ id: n.id, label: "" })));
    } else {
      applyLabelVisibility(null, params.scale);
    }
    applyStyles();
    doDrawHullOverlay();
  });

  if (fitBtn) {
    fitBtn.addEventListener("click", () => {
      network.fit({ animation: { duration: 350, easingFunction: "easeInOutCubic" } });
    });
  }

  const resetFocusBtn = document.getElementById("reset-focus-btn");
  if (resetFocusBtn) {
    resetFocusBtn.addEventListener("click", () => {
      exitSpotlight(network, {
        container,
        spotlightBg,
        applyStyles,
      });
      setState({ selectedNodeId: null, highlightMode: "none", nhopResult: null });
      clearNhopCache();
      applyStyles();
      network.fit({ animation: { duration: 280, easingFunction: "easeInOutCubic" } });
    });
  }

  if (depthSlider) {
    depthSlider.value = Math.min(5, Math.max(1, initialDepth >= 999 ? 5 : initialDepth));
    if (depthBadge) depthBadge.textContent = depthSlider.value;
    const onDepthChange = () => {
      const depth = parseInt(depthSlider.value, 10) || 1;
      setState({ selectedDepth: depth });
      if (depthBadge) depthBadge.textContent = depth;
      const fn = state.focusedNodeId || state.selectedNodeId;
      if (fn) {
        computeAndCacheNhop(fn, depth);
      } else {
        clearNhopCache();
      }
      applyStyles();
      if (fn && state.nhopResult?.nodeIds) {
        network.fit({ nodes: Array.from(state.nhopResult.nodeIds), animation: { duration: 250, easingFunction: "easeInOutCubic" } });
      }
    };
    depthSlider.addEventListener("input", onDepthChange);
    depthSlider.addEventListener("change", onDepthChange);
  }

  const edgeFilterSelect = document.getElementById("edge-filter");
  if (edgeFilterSelect) {
    edgeFilterSelect.addEventListener("change", () => {
      setState({ edgeFilter: edgeFilterSelect.value || "all" });
      applyStyles();
    });
  }

  if (edgeLabelToggle) {
    edgeLabelToggle.addEventListener("click", () => {
      setState({ showEdgeLabels: !state.showEdgeLabels });
      applyEdgeLabelMode();
    });
  }

  const detailPanelPin = document.getElementById("detail-panel-pin");
  if (detailPanelPin) {
    detailPanelPin.addEventListener("click", () => {
      const pinned = !state.panelPinned;
      setState({ panelPinned: pinned });
      detailPanelPin.setAttribute("aria-pressed", String(pinned));
      detailPanelPin.title = pinned ? "Unpin panel" : "Pin panel";
    });
  }
  if (detailPanelClose) {
    detailPanelClose.addEventListener("click", () => {
      detailPanel.classList.remove("visible");
      detailPanelClose.style.display = "none";
    });
  }

  function showNodeDetailPanel(nodeId) {
    renderNodeDetail(
      detailContent,
      nodeId,
      nodeDefaults,
      nodeAttrs,
      hierarchyLevels,
      clusters,
      network,
      edges,
      C,
      {
        onNodeLinkClick: (id) => {
          const depth = state.selectedDepth >= 999 ? 10 : state.selectedDepth;
          computeAndCacheNhop(id, depth);
          setState({ selectedNodeId: id, highlightMode: "selection" });
          applyStyles();
          showNodeDetailPanel(id);
          const relatedArr = Array.from(state.nhopResult?.nodeIds ?? []);
          if (relatedArr.length > 1) {
            network.fit({ nodes: relatedArr, animation: { duration: 300, easingFunction: "easeInOutCubic" } });
          } else {
            network.focus(id, { scale: 1.2, animation: { duration: 300 } });
          }
          detailContent.scrollTop = 0;
        },
        onExpand: (h) => {
          const d = Math.min(5, Math.max(1, h >= 999 ? 5 : h));
          setState({ selectedDepth: d });
          if (depthSlider) depthSlider.value = String(d);
          if (depthBadge) depthBadge.textContent = d;
          const fn = state.focusedNodeId || state.selectedNodeId;
          if (fn) computeAndCacheNhop(fn, h >= 999 ? 10 : h);
          else clearNhopCache();
          applyStyles();
          applyLabelVisibility();
        },
        onCollapse: () => {
          setState({ selectedNodeId: null, highlightMode: "none", nhopResult: null });
          exitSpotlight(network, { container, spotlightBg, applyStyles });
          clearNhopCache();
          applyStyles();
          applyLabelVisibility();
          detailPanel.classList.remove("visible");
          if (detailPanelClose) detailPanelClose.style.display = "none";
        },
      }
    );
    detailPanel.classList.add("visible");
    if (detailPanelClose) detailPanelClose.style.display = "block";
  }

  network.on("click", (params) => {
    if (params.edges && params.edges.length > 0) {
      renderEdgeDetail(detailContent, params.edges[0], edges, edgeAttrs, C, {
        onFlagIncorrect: () => showToast("Flagged for review", "info"),
      });
      detailPanel.classList.add("visible");
      if (detailPanelClose) detailPanelClose.style.display = "block";
      return;
    }
    if (!params.nodes || params.nodes.length === 0) {
      if (state.focusedNodeId) {
        exitSpotlight(network, { container, spotlightBg, applyStyles });
      } else {
        setState({ selectedNodeId: null, highlightMode: "none", nhopResult: null });
        applyStyles();
        if (!state.panelPinned) {
          detailPanel.classList.remove("visible");
          if (detailPanelClose) detailPanelClose.style.display = "none";
        }
      }
      return;
    }
    const nodeId = params.nodes[0];
    if (state.highlightMode === "spotlight" && state.focusedNodeId === nodeId) return;
    if (state.focusedNodeId && nodeId !== state.focusedNodeId) {
      exitSpotlight(network, { container, spotlightBg, applyStyles });
    }
    const depth = state.selectedDepth >= 999 ? 10 : state.selectedDepth;
    computeAndCacheNhop(nodeId, depth);
    let hist = [...(state.selectionHistory || [])];
    if (hist[hist.length - 1] !== nodeId) {
      hist.push(nodeId);
      if (hist.length > 20) hist = hist.slice(-20);
    }
    setState({ selectedNodeId: nodeId, highlightMode: "selection", selectionHistory: hist });
    applyStyles();
    showNodeDetailPanel(nodeId);
    const relatedArr = Array.from(state.nhopResult?.nodeIds ?? []);
    if (relatedArr.length > 1) {
      network.fit({ nodes: relatedArr, animation: { duration: 280, easingFunction: "easeInOutCubic" } });
    } else {
      network.focus(nodeId, { scale: 1.2, animation: { duration: 280, easingFunction: "easeInOutCubic" } });
    }
  });

  network.on("hoverNode", (params) => {
    const id = params.node;
    setState({ hoveredNodeId: id });
    const meta = nodeDefaults[id] || {};
    const stats = buildNodeRelationSummary(network, id, edges);
    const domPoint =
      params.event?.pointer?.DOM || network.canvasToDOM(network.getPositions([id])[id] || { x: 0, y: 0 });
    showTooltip(tooltip, { id, ...meta }, stats, domPoint, container);
    applyStyles();
  });

  network.on("blurNode", () => {
    hideTooltip(tooltip);
    setState({ hoveredNodeId: null });
    applyStyles();
  });

  network.on("hoverEdge", (params) => {
    if (state.focusedNodeId) return;
    setState({ hoveredEdgeId: params.edge });
    const edge = edges.get(params.edge);
    if (!edge) return;
    const hoverDashes = edge.isDimmed ? [2, 4] : [7, 5];
    const hoverWidth = edge.isDimmed ? 0.8 : Math.max(2.8, edge.width || 2.6);
    edges.update([
      {
        id: edge.id,
        dashes: hoverDashes,
        width: hoverWidth,
        label: edgeLabelsOnHoverOnly ? (edge.relation || edge.label || "related_to") : getRelationLabel(edge),
      },
    ]);
    applyStyles();
  });

  network.on("blurEdge", () => {
    if (state.focusedNodeId) return;
    setState({ hoveredEdgeId: null });
    applyStyles();
  });

  network.on("doubleClick", (params) => {
    if (!params.nodes || params.nodes.length === 0) {
      exitSpotlight(network, { container, spotlightBg, applyStyles });
      return;
    }
    enterSpotlight(network, params.nodes[0], {
      container,
      spotlightBg,
      DEBUG,
      applyStyles,
      applyLabelVisibility,
      computeAndCacheNhop,
    });
  });

  if (hubIds.size > 0) {
    const hubBtn = document.getElementById("hub-edges-toggle");
    if (hubBtn) {
      hubBtn.style.display = "flex";
      hubBtn.textContent = state.showAllHubEdges ? "Cap hub edges" : "Show all connections";
      hubBtn.addEventListener("click", () => {
        setState({ showAllHubEdges: !state.showAllHubEdges });
        hubBtn.textContent = state.showAllHubEdges ? "Cap hub edges" : "Show all connections";
        applyStyles();
      });
    }
  }

  const viewModeSelect = document.getElementById("view-mode-select");
  if (viewModeSelect) {
    viewModeSelect.addEventListener("change", () => {
      setState({ viewMode: viewModeSelect.value });
      const allNodes = nodes.get();
      const nodeUpdates = allNodes.map((n) => {
        let hide = false;
        if (state.viewMode === "classes") hide = n.kind === "instance";
        else if (state.viewMode === "instances") hide = n.kind !== "instance";
        return { id: n.id, hidden: hide };
      });
      if (nodeUpdates.length) nodes.update(nodeUpdates);
      applyStyles();
      runGalaxyLayout();
    });
  }

  const isolated = data.isolated || [];

  function runGalaxyLayout() {
    galaxyLayout(network, nodes, edges, clusters, {
      isolated,
      progressBar,
      progressWrap,
      container,
      C,
      nodeCount,
      onComplete: () => {
        applyLabelVisibility();
        applyStyles();
        doDrawHullOverlay();
      },
      createMinimap: () => {
        if (nodeCount > 100 && nodeCount <= 300) {
          const minimapEl = document.getElementById("minimap");
          createMinimap(minimapEl, network, nodes, edges, C);
        }
      },
    });
  }

  network.on("stabilizationIterationsDone", () => {
    setState({ simulationFrozen: true });
    if (progressBar) progressBar.style.width = "100%";
    if (progressWrap) progressWrap.style.display = "none";
    if (DEBUG) {
      const pos = network.getPositions();
      const ids = Object.keys(pos);
      let nanCount = 0;
      ids.forEach((id) => {
        const p = pos[id];
        if (p && (isNaN(p.x) || isNaN(p.y))) nanCount++;
      });
      debugLog(DEBUG, "Layout done. Positions: NaN=" + nanCount);
    }
    network.fit({ animation: { duration: 350, easingFunction: "easeInOutCubic" } });
    requestAnimationFrame(() => {
      container.classList.add("ready");
      applyLabelVisibility();
      applyStyles();
      doDrawHullOverlay();
      if (nodeCount > 100 && nodeCount <= 300) {
        const minimapEl = document.getElementById("minimap");
        createMinimap(minimapEl, network, nodes, edges, C);
      }
    });
  });

  applyStyles();
  applyLabelVisibility();
  applyEdgeLabelMode();
  applyStyles();

  setTimeout(runGalaxyLayout, 0);

  if (preSelectNode && nodeCount > 0) {
    const found = nodes.get().some((n) => n.id === preSelectNode);
    if (found) {
      setTimeout(() => {
        enterSpotlight(network, preSelectNode, {
          container,
          spotlightBg,
          DEBUG,
          applyStyles,
          applyLabelVisibility,
          computeAndCacheNhop,
        });
        network.focus(preSelectNode, { scale: 1.2, animation: { duration: 400, easingFunction: "easeInOutCubic" } });
      }, 500);
    }
  }

  document.addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") {
      if (ev.key === "Escape") ev.target.blur();
      if (ev.key === "k" && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        document.getElementById("node-search")?.focus();
      }
      return;
    }
    if (ev.key === "Escape") {
      if (state.focusedNodeId) {
        exitSpotlight(network, { container, spotlightBg, applyStyles });
      } else if (state.selectedNodeId) {
        setState({ selectedNodeId: null, highlightMode: "none", nhopResult: null });
        applyStyles();
        if (!state.panelPinned) {
          detailPanel.classList.remove("visible");
          if (detailPanelClose) detailPanelClose.style.display = "none";
        }
      }
      document.getElementById("node-search")?.blur();
    } else if (ev.key === "k" && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      document.getElementById("node-search")?.focus();
    } else if (ev.key === "f" || ev.key === "F") {
      if (!ev.ctrlKey && !ev.metaKey) {
        ev.preventDefault();
        network.fit({ animation: { duration: 350, easingFunction: "easeInOutCubic" } });
      }
    } else if (ev.key === "h" || ev.key === "H") {
      if (hubIds.size > 0 && !ev.ctrlKey && !ev.metaKey) {
        ev.preventDefault();
        setState({ showAllHubEdges: !state.showAllHubEdges });
        const hubBtn = document.getElementById("hub-edges-toggle");
        if (hubBtn) hubBtn.textContent = state.showAllHubEdges ? "Cap hub edges" : "Show all connections";
        applyStyles();
      }
    } else if (ev.key === "l" || ev.key === "L") {
      if (!ev.ctrlKey && !ev.metaKey) {
        ev.preventDefault();
        setState({ showEdgeLabels: !state.showEdgeLabels });
        applyEdgeLabelMode();
      }
    } else if (ev.key >= "1" && ev.key <= "5") {
      ev.preventDefault();
      const d = parseInt(ev.key, 10);
      setState({ selectedDepth: d });
      if (depthSlider) depthSlider.value = String(d);
      if (depthBadge) depthBadge.textContent = d;
      const fn = state.focusedNodeId || state.selectedNodeId;
      if (fn) {
        computeAndCacheNhop(fn, d);
        applyStyles();
        if (state.nhopResult?.nodeIds) {
          network.fit({ nodes: Array.from(state.nhopResult.nodeIds), animation: { duration: 250, easingFunction: "easeInOutCubic" } });
        }
      }
    } else if (ev.key === "+" || ev.key === "=") {
      ev.preventDefault();
      const scale = network.getScale() * 1.2;
      network.moveTo({ scale: Math.min(scale, 5) });
    } else if (ev.key === "-") {
      ev.preventDefault();
      const scale = network.getScale() * 0.8;
      network.moveTo({ scale: Math.max(scale, 0.1) });
    } else if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
      const hist = state.selectionHistory;
      if (hist.length < 2) return;
      const idx = hist.indexOf(state.selectedNodeId);
      if (idx < 0) return;
      const nextIdx = ev.key === "ArrowRight" ? idx + 1 : idx - 1;
      if (nextIdx >= 0 && nextIdx < hist.length) {
        const id = hist[nextIdx];
        computeAndCacheNhop(id, state.selectedDepth >= 999 ? 10 : state.selectedDepth);
        setState({ selectedNodeId: id, highlightMode: "selection" });
        applyStyles();
        showNodeDetailPanel(id);
        network.focus(id, { scale: 1.2, animation: { duration: 250 } });
      }
    }
  });

  const nodeSearch = document.getElementById("node-search");
  if (nodeSearch) {
    nodeSearch.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter") return;
      const q = (nodeSearch.value || "").trim().toLowerCase();
      if (!q) return;
      const all = nodes.get();
      for (let i = 0; i < all.length; i++) {
        if (all[i].label && String(all[i].label).toLowerCase().indexOf(q) !== -1) {
          enterSpotlight(network, all[i].id, {
            container,
            spotlightBg,
            DEBUG,
            applyStyles,
            applyLabelVisibility,
            computeAndCacheNhop,
          });
          network.focus(all[i].id, { scale: 1.2, animation: { duration: 300 } });
          break;
        }
      }
    });
  }
} catch (err) {
  const initError = document.getElementById("viewer-init-error");
  const graphContainer = document.getElementById("graph");
  if (initError) {
    initError.textContent = "Graph viewer error: " + (err?.message || String(err));
    initError.classList.add("visible");
  }
  if (graphContainer) {
    graphContainer.style.opacity = "1";
    graphContainer.style.transform = "none";
  }
  console.error("[GraphViewer]", err);
}
})();
