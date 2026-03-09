/**
 * Ontology Graph Viewer - Layout engine (Galaxy, ELK, force fallback)
 */

import { CLUSTER_BORDER_COLORS, withAlpha, computeConvexHull, debugLog } from "./utils.js";
import { setState } from "./state.js";

// Phase 1–3 constants (Section 11)
export const LAYOUT = {
  MIN_NODE_SPACING: 80,
  RING_PADDING: 40,
  CELL_MARGIN: 60,
  GALAXY_PADDING: 120,
  PACK_MAX_ITER: 200,
  PACK_STEP: 0.05,
  RESOLVE_MAX_ITER: 50,
  RESOLVE_STEP: 0.5,
  HULL_PADDING: 28,
  HULL_ALPHA_FILL: 0.07,
  HULL_ALPHA_STROKE: 0.25,
  HULL_MAX_NODES: 600,
  MINIMAP_MIN_NODES: 100,
  MINIMAP_MAX_NODES: 300,
};

const {
  MIN_NODE_SPACING,
  RING_PADDING,
  CELL_MARGIN,
  GALAXY_PADDING,
  PACK_MAX_ITER,
  PACK_STEP,
  RESOLVE_MAX_ITER,
  RESOLVE_STEP,
  HULL_MAX_NODES,
} = LAYOUT;

function estimateClusterRadius(n) {
  const rings = Math.ceil((-1 + Math.sqrt(1 + (4 * n) / 6)) / 2);
  return rings * (MIN_NODE_SPACING + RING_PADDING) + MIN_NODE_SPACING;
}

function packCircles(cells, maxIter, step) {
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (let i = 0; i < cells.length; i++) {
      for (let j = i + 1; j < cells.length; j++) {
        const A = cells[i];
        const B = cells[j];
        const dx = B.centroid.x - A.centroid.x;
        const dy = B.centroid.y - A.centroid.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.001;
        const minD = A.radius + B.radius + CELL_MARGIN;
        if (d < minD) {
          const push = (minD - d) * step;
          const nx = dx / d;
          const ny = dy / d;
          A.centroid.x -= nx * push;
          A.centroid.y -= ny * push;
          B.centroid.x += nx * push;
          B.centroid.y += ny * push;
          moved = true;
        }
      }
    }
    for (let i = 0; i < cells.length; i++) {
      const c = cells[i].centroid;
      c.x *= 0.998;
      c.y *= 0.998;
    }
    if (!moved) break;
  }
}

function placeNodesOnRings(cell, sortedNodes) {
  const pos = {};
  let ring = 0;
  let slot = 0;
  let capacity = 6;
  const cx = cell.centroid.x;
  const cy = cell.centroid.y;
  for (let i = 0; i < sortedNodes.length; i++) {
    const node = sortedNodes[i];
    if (slot === capacity) {
      ring++;
      capacity = Math.floor(
        (2 * Math.PI * ring * (MIN_NODE_SPACING + RING_PADDING)) / MIN_NODE_SPACING
      );
      slot = 0;
    }
    const angle =
      (2 * Math.PI * slot) / capacity + ring * 0.3;
    const r = ring * (MIN_NODE_SPACING + RING_PADDING);
    pos[node.id] = {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
    slot++;
  }
  return pos;
}

function placeIsolatedNodes(isolated, outerR) {
  const pos = {};
  const n = isolated.length;
  if (n === 0) return pos;
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i) / n;
    pos[isolated[i]] = {
      x: outerR * Math.cos(angle),
      y: outerR * Math.sin(angle),
    };
  }
  return pos;
}

function resolveNodeOverlaps(pos, nodeRadii) {
  const entries = Object.entries(pos).map(([id, p]) => ({ id, x: p.x, y: p.y, r: nodeRadii[id] ?? 20 }));
  const minGap = 8;
  for (let iter = 0; iter < RESOLVE_MAX_ITER; iter++) {
    let changed = false;
    for (let i = 0; i < entries.length; i++) {
      for (let j = i + 1; j < entries.length; j++) {
        const A = entries[i];
        const B = entries[j];
        const dx = B.x - A.x;
        const dy = B.y - A.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.001;
        const minD = (A.r || 20) + (B.r || 20) + minGap;
        if (d < minD) {
          const push = ((minD - d) * RESOLVE_STEP) / 2;
          const nx = dx / d;
          const ny = dy / d;
          A.x -= nx * push;
          A.y -= ny * push;
          B.x += nx * push;
          B.y += ny * push;
          pos[A.id] = { x: A.x, y: A.y };
          pos[B.id] = { x: B.x, y: B.y };
          changed = true;
        }
      }
    }
    if (!changed) break;
  }
}

export function runGalaxyLayout(nodes, edges, clusters, isolated, options = {}) {
  const { onComplete, progressBar, progressWrap } = options;
  const visibleNodes = nodes.get().filter((n) => !n.hidden);
  const nodeIds = new Set(visibleNodes.map((n) => n.id));
  const nodeMap = {};
  visibleNodes.forEach((n) => {
    nodeMap[n.id] = n;
  });

  const clusterList = [];
  if (clusters && clusters.length > 0) {
    clusters.forEach((c) => {
      const members = (Array.isArray(c) ? c : []).filter((nid) => nodeIds.has(nid));
      if (members.length > 0) clusterList.push(members);
    });
  }
  const isolatedSet = new Set(isolated || []);
  const isolatedVisible = (isolated || []).filter((nid) => nodeIds.has(nid));
  const clusteredIds = new Set(clusterList.flat());
  const unclustered = visibleNodes.filter(
    (n) => !clusteredIds.has(n.id) && !isolatedSet.has(n.id)
  );
  if (unclustered.length > 0) {
    clusterList.push(unclustered.map((n) => n.id));
  }

  const cells = clusterList.map((members) => ({
    members,
    radius: estimateClusterRadius(members.length),
    centroid: { x: 0, y: 0 },
  }));

  cells.sort((a, b) => b.radius - a.radius);
  if (cells.length > 0) {
    cells[0].centroid = { x: 0, y: 0 };
    let dist = cells[0].radius;
    for (let i = 1; i < cells.length; i++) {
      dist += cells[i].radius + CELL_MARGIN;
      const angle = (2 * Math.PI * i) / cells.length;
      cells[i].centroid = { x: dist * Math.cos(angle), y: dist * Math.sin(angle) };
    }
  }
  packCircles(cells, PACK_MAX_ITER, PACK_STEP);

  const pos = {};
  for (let c = 0; c < cells.length; c++) {
    const cell = cells[c];
    const sorted = cell.members
      .map((nid) => nodeMap[nid])
      .filter(Boolean)
      .sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0));
    const sub = placeNodesOnRings(cell, sorted);
    Object.assign(pos, sub);
  }

  let outerR = 0;
  for (let c = 0; c < cells.length; c++) {
    const cx = cells[c].centroid.x;
    const cy = cells[c].centroid.y;
    const r = cells[c].radius;
    outerR = Math.max(outerR, Math.sqrt(cx * cx + cy * cy) + r);
  }
  outerR += GALAXY_PADDING;
  Object.assign(pos, placeIsolatedNodes(isolatedVisible, outerR));

  const nodeRadii = {};
  visibleNodes.forEach((n) => {
    const s = n.size ?? 20;
    nodeRadii[n.id] = Math.max(20, s / 2);
  });
  resolveNodeOverlaps(pos, nodeRadii);

  if (Object.keys(pos).length > 0) {
    const updates = Object.entries(pos).map(([id, p]) => ({
      id,
      x: p.x,
      y: p.y,
      fixed: { x: true, y: true },
    }));
    nodes.update(updates);
  }
  setState({ simulationFrozen: true });

  if (progressBar) progressBar.style.width = "100%";
  if (progressWrap) progressWrap.style.display = "none";

  const nodeIdsToFit = Object.keys(pos);
  if (onComplete) onComplete(nodeIdsToFit);
}

export function galaxyLayout(network, nodes, edges, clusters, config) {
  const isolated = config.isolated || [];
  runGalaxyLayout(nodes, edges, clusters, isolated, {
    ...config,
    onComplete: (nodeIdsToFit) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          network.setOptions({ physics: { enabled: false } });
          network.fit({
            nodes: nodeIdsToFit && nodeIdsToFit.length ? nodeIdsToFit : undefined,
            animation: { duration: 350, easingFunction: "easeInOutCubic" },
          });
          if (config.container) config.container.classList.add("ready");
          if (config.onComplete) config.onComplete();
          if (config.createMinimap) config.createMinimap();
        });
      });
    },
  });
}

export function drawHullOverlay(network, clusters, hullCanvas, C, nodeCount) {
  if (!hullCanvas || !clusters || clusters.length === 0 || nodeCount > HULL_MAX_NODES) {
    if (nodeCount > HULL_MAX_NODES && typeof console !== "undefined") {
      console.info("[GraphViewer] Hull overlay skipped (nodeCount > " + HULL_MAX_NODES + ")");
    }
    return;
  }
  const ctx = hullCanvas.getContext("2d");
  const rect = hullCanvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  hullCanvas.width = rect.width;
  hullCanvas.height = rect.height;
  ctx.clearRect(0, 0, rect.width, rect.height);
  const pos = network.getPositions();
  for (let c = 0; c < clusters.length; c++) {
    const clusterNodes = clusters[c];
    const pts = [];
    for (let i = 0; i < clusterNodes.length; i++) {
      const p = pos[clusterNodes[i]];
      if (p) {
        const dom = network.canvasToDOM({ x: p.x, y: p.y });
        pts.push({ x: dom.x - rect.left, y: dom.y - rect.top });
      }
    }
    if (pts.length >= 2) {
      const hull = computeConvexHull(pts);
      const baseColor = CLUSTER_BORDER_COLORS[c % CLUSTER_BORDER_COLORS.length];
      ctx.fillStyle = withAlpha(baseColor, LAYOUT.HULL_ALPHA_FILL);
      ctx.strokeStyle = withAlpha(baseColor, LAYOUT.HULL_ALPHA_STROKE);
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(hull[0].x, hull[0].y);
      for (let h = 1; h < hull.length; h++) ctx.lineTo(hull[h].x, hull[h].y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}

export function elkLayout(network, nodes, edges, hasCycles, config) {
  const { DEBUG, onFallback } = config;
  const ELK = window.ELK;
  if (typeof ELK === "undefined") return;

  if (hasCycles) {
    if (DEBUG) debugLog(DEBUG, "Graph has cycles, falling back to force layout");
    setState({ layoutMode: "force" });
    const repulsion = -12000;
    const springLen = 220;
    network.setOptions({ physics: { enabled: true }, layout: { hierarchical: { enabled: false } } });
    network.setOptions({
      physics: {
        barnesHut: {
          gravitationalConstant: repulsion,
          centralGravity: 0.02,
          springLength: springLen,
          springConstant: 0.03,
          damping: 0.45,
          avoidOverlap: 1,
        },
        stabilization: { enabled: true, iterations: 500, updateInterval: 25, fit: true },
      },
    });
    setState({ simulationFrozen: false });
    network.once("stabilizationIterationsDone", () => {
      network.setOptions({ physics: { enabled: false } });
      setState({ simulationFrozen: true });
      network.fit({ animation: { duration: 300, easingFunction: "easeInOutCubic" } });
    });
    return;
  }

  const elk = new ELK();
  const visibleNodes = nodes.get().filter((n) => !n.hidden);
  const visibleEdges = edges.get().filter((e) => !e.hidden);
  const nodeIds = new Set(visibleNodes.map((n) => n.id));
  const normalizedEdges = visibleEdges
    .filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to) && e.from !== e.to)
    .map((e) => ({ id: String(e.id), sources: [String(e.from)], targets: [String(e.to)] }));
  const nodeWidth = 140;
  const nodeHeight = 40;
  const elkGraph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "50",
      "elk.layered.spacing.nodeNodeBetweenLayers": "100",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.allowNonTreeEdges": "true",
    },
    children: visibleNodes.map((n) => ({
      id: String(n.id),
      width: n.width != null && n.width > 0 ? n.width : nodeWidth,
      height: n.height != null && n.height > 0 ? n.height : nodeHeight,
    })),
    edges: normalizedEdges,
  };

  elk
    .layout(elkGraph)
    .then((layout) => {
      if (!layout || !layout.children || layout.children.length === 0) {
        if (DEBUG) debugLog(DEBUG, "ELK returned empty layout, fallback to force");
        if (onFallback) onFallback();
        return;
      }
      const pos = {};
      let allSame = true;
      let firstX = null;
      let firstY = null;
      layout.children.forEach((c) => {
        const x = c.x != null ? c.x : 0;
        const y = c.y != null ? c.y : 0;
        pos[c.id] = { x, y };
        if (firstX == null) {
          firstX = x;
          firstY = y;
        } else if (x !== firstX || y !== firstY) allSame = false;
      });
      if (Object.keys(pos).length === 0) {
        if (DEBUG) debugLog(DEBUG, "ELK produced no positions, fallback to force");
        if (onFallback) onFallback();
        return;
      }
      if (allSame && Object.keys(pos).length > 1) {
        if (DEBUG) debugLog(DEBUG, "ELK returned identical coordinates, fallback to force");
        if (onFallback) onFallback();
        return;
      }
      const updates = Object.entries(pos).map(([id, p]) => ({
        id,
        x: p.x,
        y: p.y,
        fixed: true,
      }));
      nodes.update(updates);
      network.setOptions({ physics: { enabled: false } });
      setState({ simulationFrozen: true, layoutMode: "elk" });
      const nodeIdsToFit = Object.keys(pos);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          network.fit({
            nodes: nodeIdsToFit.length ? nodeIdsToFit : undefined,
            animation: { duration: 300, easingFunction: "easeInOutCubic" },
          });
        });
      });
    })
    .catch((err) => {
      if (DEBUG) debugLog(DEBUG, "ELK layout failed:", err);
      if (onFallback) onFallback();
    });
}
