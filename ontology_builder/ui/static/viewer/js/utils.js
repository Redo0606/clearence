/**
 * Ontology Graph Viewer - Utility functions
 */

export function escHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function withAlpha(hex, alpha) {
  const clean = String(hex || "").replace("#", "");
  if (clean.length !== 6) return hex;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function getThemeColors() {
  const s = getComputedStyle(document.documentElement);
  const v = (name) => s.getPropertyValue("--" + name).trim();
  return {
    bgBody: v("bg-body"),
    bgSidebar: v("bg-sidebar"),
    bgCard: v("bg-card"),
    bgCardHover: v("bg-card-hover"),
    border: v("border"),
    textPrimary: v("text-primary"),
    textMuted: v("text-muted"),
    accent: v("accent"),
    accentBright: v("accent-bright"),
    accentTertiary: v("accent-tertiary"),
    accentSecondary: v("accent-secondary"),
    pending: v("pending"),
    success: v("success"),
    info: v("info"),
    errorBright: v("error-bright"),
  };
}

export const CLUSTER_BORDER_COLORS = [
  "#ff50a0", "#64b4ff", "#ffc850", "#78dcb4",
  "#c878ff", "#50d4a0", "#ff9064", "#64c8ff",
];

export const CLUSTER_PALETTE = [
  "rgba(255,80,160,0.05)", "rgba(100,180,255,0.05)",
  "rgba(255,200,80,0.05)", "rgba(120,220,180,0.05)",
];

export const HUB_EDGE_CAP = 25;

export function getClusterColor(clusterId, C) {
  if (clusterId < 0) return C.border;
  return CLUSTER_BORDER_COLORS[clusterId % CLUSTER_BORDER_COLORS.length];
}

export function buildNodeClusterMap(nodes, clusters) {
  const m = {};
  nodes.forEach((n) => {
    if (n.cluster != null && n.cluster >= 0) m[n.id] = n.cluster;
  });
  if (Object.keys(m).length === 0 && clusters && clusters.length > 0) {
    clusters.forEach((c, idx) => {
      (Array.isArray(c) ? c : []).forEach((nid) => { m[nid] = idx; });
    });
  }
  return m;
}

export function buildStaticAdjacency(edges) {
  const adj = {};
  edges.forEach((e) => {
    if (e.from && e.to) {
      adj[e.from] = adj[e.from] || [];
      if (adj[e.from].indexOf(e.to) === -1) adj[e.from].push(e.to);
      adj[e.to] = adj[e.to] || [];
      if (adj[e.to].indexOf(e.from) === -1) adj[e.to].push(e.from);
    }
  });
  return adj;
}

/** Convert backend adjacency { nodeId: [{neighbourId, edgeId, direction}, ...] } to simple { nodeId: [neighbourId, ...] }. */
export function adjacencyFromBackend(backendAdj) {
  if (!backendAdj || typeof backendAdj !== "object") return null;
  const out = {};
  for (const [nid, conns] of Object.entries(backendAdj)) {
    out[nid] = (conns || []).map((c) => c.neighbourId);
  }
  return out;
}

/**
 * Build N-hop neighbourhood. Returns { nodeIds: Set<string>, edgeIds: Set<string> }.
 * adjacency: Map<nodeId, Array<{neighbourId, edgeId, direction}>> or plain object
 */
export function buildNhopNeighbourhood(startId, depth, adjacency) {
  const nodeIds = new Set([startId]);
  const edgeIds = new Set();
  let frontier = [startId];
  const getNeighbours = (nId) => {
    if (adjacency instanceof Map) return adjacency.get(nId) ?? [];
    return adjacency[nId] ?? [];
  };
  for (let hop = 0; hop < depth; hop++) {
    const next = [];
    for (const nId of frontier) {
      for (const { neighbourId, edgeId } of getNeighbours(nId)) {
        if (edgeId) edgeIds.add(edgeId);
        if (!nodeIds.has(neighbourId)) {
          nodeIds.add(neighbourId);
          next.push(neighbourId);
        }
      }
    }
    frontier = next;
    if (frontier.length === 0) break;
  }
  return { nodeIds, edgeIds };
}

/** Build full adjacency Map from edges for buildNhopNeighbourhood. */
export function buildAdjacencyMap(edges) {
  const adj = new Map();
  edges.forEach((e) => {
    if (e.from && e.to && e.id) {
      const fromList = adj.get(e.from) || [];
      fromList.push({ neighbourId: e.to, edgeId: e.id, direction: "out" });
      adj.set(e.from, fromList);
      const toList = adj.get(e.to) || [];
      toList.push({ neighbourId: e.from, edgeId: e.id, direction: "in" });
      adj.set(e.to, toList);
    }
  });
  return adj;
}

export function debugLog(DEBUG, ...args) {
  if (DEBUG && console && console.log) {
    console.log("[GraphViewer]", ...args);
  }
}

export function showToast(message, type = "info", durationMs = 2500) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }
  const el = document.createElement("div");
  el.className = "toast toast-" + type;
  el.textContent = message;
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add("visible"));
  setTimeout(() => {
    el.classList.remove("visible");
    setTimeout(() => el.remove(), 300);
  }, durationMs);
}

/** Graham scan convex hull, O(n log n). Returns hull points in CCW order. */
export function computeConvexHull(points) {
  if (points.length < 3) return points;
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  points = [...points].sort((a, b) => (a.x !== b.x ? a.x - b.x : a.y - b.y));
  const lower = [];
  const upper = [];
  for (let i = 0; i < points.length; i++) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], points[i]) <= 0)
      lower.pop();
    lower.push(points[i]);
  }
  for (let j = points.length - 1; j >= 0; j--) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], points[j]) <= 0)
      upper.pop();
    upper.push(points[j]);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}
