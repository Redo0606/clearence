"""Graph visualization: Matplotlib PNG and interactive vis.js HTML.

Differentiates classes (rectangles/blue) from instances (circles/green),
colors edges by relation type. Uses normalized graph model for stable layout.
"""

from __future__ import annotations

import io
import json
import logging
import random
from typing import TYPE_CHECKING, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from ontology_builder.ui.graph_models import normalize_graph

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

logger = logging.getLogger(__name__)

_RELATION_COLORS: dict[str, str] = {
    "subClassOf": "#ec4899",
    "type": "#38bdf8",
    "part_of": "#38bdf8",
    "contains": "#a78bfa",
    "depends_on": "#f59e0b",
}
_DEFAULT_EDGE_COLOR = "#6b7280"

_EDGE_STYLES: dict[str, dict[str, Any]] = {
    "subClassOf": {"width": 2.2, "dashes": False, "color": "#ec4899"},
    "type": {"width": 1.6, "dashes": [6, 4], "color": "#38bdf8"},
    "instanceOf": {"width": 1.6, "dashes": [6, 4], "color": "#38bdf8"},
    "part_of": {"width": 1.5, "dashes": [4, 3], "color": "#38bdf8"},
    "contains": {"width": 1.5, "dashes": False, "color": "#a78bfa"},
    "depends_on": {"width": 1.5, "dashes": [3, 2], "color": "#f59e0b"},
}


def visualize(graph: "OntologyGraph", save_path: str | None = None) -> io.BytesIO | None:
    """Draw ontology graph as PNG with class/instance differentiation."""
    g = graph.get_graph()
    if g.number_of_nodes() == 0:
        if save_path:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Empty graph", ha="center", va="center")
            fig.savefig(save_path)
            plt.close(fig)
        return None

    pos = nx.spring_layout(g, seed=42, k=3.5)

    class_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "class"]
    instance_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "instance"]
    other_nodes = [n for n in g.nodes() if n not in class_nodes and n not in instance_nodes]

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    if class_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=class_nodes, node_color="#ec4899",
                               node_shape="s", node_size=600, ax=ax, alpha=0.9)
    if instance_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=instance_nodes, node_color="#38bdf8",
                               node_shape="o", node_size=400, ax=ax, alpha=0.9)
    if other_nodes:
        nx.draw_networkx_nodes(g, pos, nodelist=other_nodes, node_color="#bdc3c7",
                               node_shape="o", node_size=300, ax=ax, alpha=0.7)

    nx.draw_networkx_labels(g, pos, font_size=7, ax=ax)

    edge_colors = [_RELATION_COLORS.get(d.get("relation", ""), _DEFAULT_EDGE_COLOR)
                   for _, _, d in g.edges(data=True)]
    nx.draw_networkx_edges(g, pos, edge_color=edge_colors, arrows=True, arrowsize=12,
                           ax=ax, alpha=0.6, connectionstyle="arc3,rad=0.1")

    edge_labels = nx.get_edge_attributes(g, "relation")
    nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels, font_size=5, ax=ax)

    ax.set_title("Ontology Graph", fontsize=14, fontweight="bold")
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#ec4899", markersize=10, label="Class"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#38bdf8", markersize=10, label="Instance"),
        ],
        loc="upper left",
    )
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        return None

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_visjs_html(
    graph: "OntologyGraph",
    pre_select_node: str | None = None,
    depth: int = 1,
    debug: bool = False,
) -> str:
    """Generate standalone HTML page with interactive vis.js graph viewer."""
    ng = normalize_graph(graph)
    logger.info(
        "Graph normalized: %d nodes, %d edges, roots=%s, cycles=%s, disconnected=%d",
        len(ng.nodes),
        len(ng.edges),
        ng.roots[:5] if len(ng.roots) > 5 else ng.roots,
        ng.has_cycles,
        ng.disconnected_count,
    )

    rng = random.Random(42)
    NODE_WIDTH = 140
    NODE_HEIGHT = 40
    vis_nodes: list[dict[str, Any]] = []
    for n in ng.nodes:
        if n.id == "__root__":
            continue
        kind = n.type
        accent = "#ec4899" if kind == "class" else "#38bdf8" if kind == "instance" else "#8a8a94"
        level = ng.hierarchy_levels.get(n.id, 999)
        x_init = rng.uniform(-200, 200)
        y_init = level * 120 + rng.uniform(-30, 30)
        vis_nodes.append({
            "id": n.id,
            "baseLabel": n.label,
            "label": n.label,
            "kind": kind,
            "accent": accent,
            "description": n.metadata.get("description", ""),
            "x": x_init,
            "y": y_init,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
        })

    vis_edges: list[dict[str, Any]] = []
    for e in ng.edges:
        if e.source == "__root__" or e.target == "__root__":
            continue
        style = _EDGE_STYLES.get(e.relation, {"width": 1.5, "dashes": False, "color": _DEFAULT_EDGE_COLOR})
        color = style.get("color", _RELATION_COLORS.get(e.relation, _DEFAULT_EDGE_COLOR))
        vis_edges.append({
            "id": e.id,
            "from": e.source,
            "to": e.target,
            "label": e.relation,
            "relation": e.relation,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": color, "opacity": 0.96, "highlight": color, "hover": color},
            "width": style.get("width", 1.5) if not e.inferred else 1.2,
            "dashes": style.get("dashes", False),
            "smooth": {"type": "cubicBezier"},
            "font": {
                "size": 10,
                "align": "middle",
                "face": "JetBrains Mono",
                "color": "#ddd9e6",
                "background": "#14141a",
                "strokeWidth": 0,
            },
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)
    relations_json = json.dumps(sorted({e["relation"] for e in vis_edges}))
    hierarchy_json = json.dumps({n.id: ng.hierarchy_levels.get(n.id, 999) for n in ng.nodes if n.id != "__root__"})
    clusters_json = json.dumps([list(c) for c in ng.clusters])
    isolated_json = json.dumps(list(ng.isolated))
    has_cycles_json = json.dumps(ng.has_cycles)
    debug_json = json.dumps(debug)
    stats = graph.export().get("stats", {})
    rel_count = stats.get("relations") or stats.get("edges")
    if rel_count is None:
        rel_count = len(vis_edges)
    cluster_info = f"Clusters: {len(ng.clusters)}" if ng.clusters else ""
    isolated_info = f"Isolated: {len(ng.isolated)}" if ng.isolated else ""
    stats_html = (
        f"Classes: {stats.get('classes', 0)} | "
        f"Instances: {stats.get('instances', 0)} | "
        f"Relations: {rel_count} | "
        f"Axioms: {stats.get('axioms', 0)}"
        + (f" | {cluster_info}" if cluster_info else "")
        + (f" | {isolated_info}" if isolated_info else "")
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ontology Graph Viewer</title>
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js" onerror="window.__viewerScriptError=true"></script>
  <script src="https://unpkg.com/elkjs@0.9.1/lib/elk.bundled.js" onerror="window.__elkScriptError=true"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{ font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif; background: #0a0a0f; color: #e8e6e3; min-height: 100vh; -webkit-font-smoothing: antialiased; }}
    button, select, input {{ font: inherit; font-family: inherit; }}
    button {{ -webkit-appearance: none; -moz-appearance: none; appearance: none; background: none; border: none; cursor: pointer; }}
    select {{ -webkit-appearance: none; -moz-appearance: none; appearance: none; background: #1e1e28; border: 1px solid #2a2a3a; border-radius: 6px; padding: 6px 10px; cursor: pointer; color: #e8e6e3; transition: border-color 0.2s ease, background 0.2s ease; }}
    select:hover {{ border-color: rgba(236,72,153,0.4); background: rgba(236,72,153,0.06); }}
    select:focus {{ outline: none; border-color: rgba(56,189,248,0.6); background: rgba(56,189,248,0.08); }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    #app {{ min-height: 100vh; height: 100%; display: flex; flex-direction: column; }}
    #header {{ padding: 14px 22px; background: #14141a; border-bottom: 1px solid #1a1a24; display: flex; justify-content: space-between; align-items: center; gap: 18px; }}
    #header h1 {{ font-size: 18px; font-weight: 600; color: #e8e6e3; }}
    #stats {{ font-size: 12px; color: #8a8a94; margin-top: 3px; }}
    #controls {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .ctrl-item {{ display: flex; align-items: center; gap: 6px; font-size: 11px; color: #8a8a94; background: #1e1e28; border: 1px solid #2a2a3a; border-radius: 8px; padding: 8px 12px; transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease, box-shadow 0.15s ease; }}
    .ctrl-item:hover {{ border-color: rgba(236,72,153,0.4); color: #e8e6e3; background: rgba(236,72,153,0.06); }}
    .ctrl-item:active {{ border-color: rgba(236,72,153,0.5); background: rgba(236,72,153,0.1); }}
    .ctrl-btn {{ cursor: pointer; padding: 8px 12px; border-radius: 8px; background: #1e1e28; border: 1px solid #2a2a3a; color: #8a8a94; transition: all 0.2s ease; }}
    .ctrl-btn:hover {{ border-color: rgba(236,72,153,0.4); color: #e8e6e3; background: rgba(236,72,153,0.06); }}
    .ctrl-btn:active {{ border-color: rgba(236,72,153,0.5); background: rgba(236,72,153,0.1); color: #f472b6; }}
    .ctrl-btn.active {{ border-color: rgba(56,189,248,0.6); color: #7dd3fc; background: rgba(56,189,248,0.08); }}
    .ctrl-sep {{ width: 1px; height: 20px; background: #2a2a3a; margin: 0 2px; flex-shrink: 0; }}
    .legend-dot {{ width: 11px; height: 11px; border-radius: 2px; flex-shrink: 0; }}
    #graph-wrap {{ flex: 1; min-height: 0; padding: 12px; position: relative; display: flex; flex-direction: column; }}
    #graph {{
      flex: 1;
      min-height: 300px;
      width: 100%;
      height: calc(100vh - 84px);
      border: 1px solid #1a1a24;
      border-radius: 12px;
      background: #0a0a0f;
      position: relative;
      z-index: 1;
      opacity: 0;
      transform: translateY(6px);
      transition: opacity 0.38s ease, transform 0.38s ease, background 0.35s ease;
    }}
    #graph.ready {{ opacity: 1; transform: translateY(0); }}
    #spotlight-bg {{
      position: absolute;
      top: 12px; left: 12px; right: 12px; bottom: 12px;
      border-radius: 12px;
      z-index: 0;
      opacity: 0;
      pointer-events: none;
      background-size: 100% 100%;
      background-repeat: no-repeat;
      background-position: center;
      filter: blur(4px) brightness(0.18);
      transition: opacity 0.4s ease;
    }}
    #spotlight-bg.active {{ opacity: 1; }}
    #node-tooltip {{
      position: absolute;
      z-index: 20;
      pointer-events: none;
      min-width: 180px;
      max-width: 300px;
      padding: 8px 10px;
      border-radius: 8px;
      background: #1e1e28;
      border: 1px solid #2a2a3a;
      color: #e8e6e3;
      box-shadow: 0 8px 22px rgba(0, 0, 0, 0.45);
      font-size: 12px;
      line-height: 1.45;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity 0.16s ease, transform 0.16s ease;
    }}
    #node-tooltip.visible {{ opacity: 1; transform: translateY(0); }}
    #node-tooltip .kind {{ font-size: 11px; color: #8a8a94; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.04em; }}
    #node-tooltip .name {{ font-weight: 600; margin-bottom: 4px; }}
    #node-tooltip .stats {{ margin: 6px 0; display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 6px; }}
    #node-tooltip .stat {{ background:#14141a; border:1px solid #2a2a3a; border-radius:6px; padding:4px 6px; text-align:center; }}
    #node-tooltip .stat .v {{ display:block; font-size:11px; font-weight:600; color:#f3f0f8; }}
    #node-tooltip .stat .k {{ display:block; margin-top:1px; font-size:10px; color:#8a8a94; }}
    #node-tooltip .rels {{ margin-top: 6px; display:flex; flex-wrap:wrap; gap:4px; }}
    #node-tooltip .rel-pill {{ font-size:10px; font-family:'JetBrains Mono', monospace; color:#f1c0dc; background:rgba(236,72,153,0.14); border:1px solid rgba(236,72,153,0.28); border-radius:999px; padding:2px 6px; }}
    #node-tooltip .desc {{ color: #c7c5d0; }}
    #viewer-init-error {{
      position: absolute;
      z-index: 25;
      top: 24px;
      left: 24px;
      right: 24px;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid rgba(236, 72, 153, 0.45);
      background: rgba(30, 10, 22, 0.95);
      color: #ffd9e8;
      font-size: 12px;
      line-height: 1.45;
      display: none;
    }}
    #viewer-init-error.visible {{ display: block; }}
  </style>
</head>
<body>
  <div id="app">
    <div id="header">
      <div>
        <h1>Ontology Graph Viewer</h1>
        <div id="stats" class="font-mono">{stats_html}</div>
      </div>
      <div id="controls">
        <div class="ctrl-item"><div class="legend-dot" style="background:#ec4899"></div> Class</div>
        <div class="ctrl-item"><div class="legend-dot" style="background:#38bdf8"></div> Instance</div>
        <div class="ctrl-sep"></div>
        <label class="ctrl-item" style="display: flex; align-items: center; gap: 4px;">
          <span style="color: #8a8a94; font-size: 10px;">Layout:</span>
          <select id="layout-select" class="text-xs font-mono">
            <option value="force" selected>Force</option>
            <option value="hierarchical">Hierarchy</option>
            <option value="elk">ELK Layered</option>
          </select>
        </label>
        <div class="ctrl-sep"></div>
        <label class="ctrl-item" style="display: flex; align-items: center; gap: 4px;">
          <span style="color: #8a8a94; font-size: 10px;">View:</span>
          <select id="view-mode-select" class="text-xs font-mono">
            <option value="full" selected>Full</option>
            <option value="classes">Classes only</option>
            <option value="instances">Instances</option>
          </select>
        </label>
        <div class="ctrl-sep"></div>
        <label class="ctrl-item" style="display: flex; align-items: center; gap: 4px;">
          <span style="color: #8a8a94; font-size: 10px;">Edges:</span>
          <select id="edge-filter" class="text-xs font-mono" style="min-width: 100px;">
            <option value="all">All</option>
            <option value="subClassOf">subClassOf only</option>
            <option value="type">type only</option>
            <option value="other">Other relations</option>
          </select>
        </label>
        <div class="ctrl-sep"></div>
        <label class="ctrl-item" style="display: flex; align-items: center; gap: 4px;">
          <span style="color: #8a8a94; font-size: 10px;">N-hop:</span>
          <select id="depth-select" class="text-xs font-mono">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="999">All</option>
          </select>
        </label>
        <div class="ctrl-sep"></div>
        <button id="fit-btn" class="ctrl-item ctrl-btn" type="button">Fit</button>
        <button id="reset-focus-btn" class="ctrl-item ctrl-btn" type="button">Reset</button>
        <div class="ctrl-sep"></div>
        <button id="edge-label-toggle" class="ctrl-item ctrl-btn" type="button">Labels: ON</button>
      </div>
    </div>
    <div id="graph-wrap">
      <div id="spotlight-bg"></div>
      <div id="graph"></div>
      <div id="node-tooltip"></div>
      <div id="viewer-init-error"></div>
    </div>
  </div>
  <script>
    var initError = document.getElementById("viewer-init-error");
    var graphContainer = document.getElementById("graph");
    function showInitError(message) {{
      if (initError) {{
        initError.textContent = message;
        initError.classList.add("visible");
      }}
      if (graphContainer) {{
        graphContainer.style.opacity = "1";
        graphContainer.style.transform = "none";
      }}
    }}
    if (typeof vis === "undefined" || !vis.DataSet || !vis.Network) {{
      showInitError("Graph viewer assets failed to load. Check network access to unpkg.com and refresh the page.");
      throw new Error("vis-network library unavailable");
    }}

    var nodes = new vis.DataSet({nodes_json});
    var edges = new vis.DataSet({edges_json});

    var container = document.getElementById("graph");
    var tooltip = document.getElementById("node-tooltip");
    var edgeLabelToggle = document.getElementById("edge-label-toggle");
    var fitBtn = document.getElementById("fit-btn");
    var spotlightBg = document.getElementById("spotlight-bg");
    var data = {{ nodes: nodes, edges: edges }};
    var showEdgeLabels = true;
    var focusedNodeId = null;

    function escHtml(text) {{
      return String(text || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function withAlpha(hex, alpha) {{
      var clean = String(hex || "").replace("#", "");
      if (clean.length !== 6) return hex;
      var r = parseInt(clean.slice(0, 2), 16);
      var g = parseInt(clean.slice(2, 4), 16);
      var b = parseInt(clean.slice(4, 6), 16);
      return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
    }}

    function easeInOutCubic(t) {{
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }}

    var nodeDefaults = {{}};
    var edgeDefaults = {{}};
    nodes.forEach(function(n) {{
      nodeDefaults[n.id] = {{
        accent: n.accent || "#ec4899",
        kind: n.kind || "class",
        description: n.description || "",
      }};
    }});
    edges.forEach(function(e) {{
      edgeDefaults[e.id] = {{
        color: (e.color && e.color.color) ? e.color.color : "#6b7280",
        dashes: e.dashes || false,
      }};
    }});

    /* ── Network setup ───────────────────────────────────────── */

    var DEBUG = {debug_json};
    var allRelations = {relations_json};
    var hierarchyLevels = {hierarchy_json};
    var clusters = {clusters_json};
    var isolated = {isolated_json};
    var hasCycles = {has_cycles_json};

    var edgeFilter = "all";
    var selectedDepth = 1;
    var layoutMode = "force";
    var simulationFrozen = false;
    var nhopCache = {{}};

    function getConnectedNodesNHop(nodeId, hops) {{
      var key = nodeId + ":" + hops;
      if (nhopCache[key]) return nhopCache[key];
      var result = new Set([nodeId]);
      var frontier = new Set([nodeId]);
      for (var h = 0; h < hops; h++) {{
        var next = new Set();
        frontier.forEach(function(nid) {{
          var conn = network.getConnectedNodes(nid) || [];
          conn.forEach(function(c) {{ next.add(c); result.add(c); }});
        }});
        frontier = next;
      }}
      nhopCache[key] = result;
      return result;
    }}

    function getConnectedEdgesForNodes(nodeSet) {{
      var edgeSet = new Set();
      nodeSet.forEach(function(nid) {{
        (network.getConnectedEdges(nid) || []).forEach(function(eid) {{ edgeSet.add(eid); }});
      }});
      return edgeSet;
    }}

    function debugLog() {{
      if (DEBUG && console && console.log) {{
        var args = Array.prototype.slice.call(arguments);
        console.log.apply(console, ["[GraphViewer]"].concat(args));
      }}
    }}

    debugLog("Nodes:", nodes.get().length, "Edges:", edges.get().length);
    nodes.get().slice(0, 5).forEach(function(n) {{
      debugLog("Node", n.id, n.label);
    }});

    var options = {{
      autoResize: true,
      layout: {{ improvedLayout: true }},
      physics: {{
        enabled: true,
        barnesHut: {{
          gravitationalConstant: -2800,
          centralGravity: 0.35,
          springLength: 140,
          springConstant: 0.06,
          damping: 0.12,
          avoidOverlap: 0.25,
        }},
        stabilization: {{
          enabled: true,
          iterations: Math.min(nodes.get().length > 200 ? 150 : 300, 400),
          updateInterval: 50,
          fit: true,
        }},
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 999999,
        navigationButtons: false,
        keyboard: true,
        dragNodes: true,
        zoomView: true,
        dragView: true,
      }},
      nodes: {{
        shape: "box",
        shapeProperties: {{ borderRadius: 8 }},
        margin: {{ top: 10, right: 12, bottom: 10, left: 12 }},
        widthConstraint: {{ minimum: 140, maximum: 280 }},
        font: {{ color: "#e8e6e3", size: 13, face: "Space Grotesk" }},
        borderWidth: 1.2,
        borderWidthSelected: 2.2,
        color: {{
          background: "#1e1e28",
          border: "#2a2a3a",
          highlight: {{ background: "#1e1e28", border: "#ec4899" }},
          hover: {{ background: "#1e1e28", border: "#ec4899" }}
        }}
      }},
      edges: {{
        smooth: {{ type: "continuous" }},
        width: 1.8,
        hoverWidth: 2.4,
        selectionWidth: 2.2,
        arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
        labelHighlightBold: true,
        color: {{ inherit: false }}
      }},
      configure: false
    }};
    var network = new vis.Network(container, data, options);

    /* ── Fit button ──────────────────────────────────────────── */

    if (fitBtn) {{
      fitBtn.addEventListener("click", function() {{
        network.fit({{ animation: {{ duration: 350, easingFunction: "easeInOutCubic" }} }});
      }});
    }}

    var resetFocusBtn = document.getElementById("reset-focus-btn");
    if (resetFocusBtn) {{
      resetFocusBtn.addEventListener("click", function() {{
        exitSpotlight();
        resetHighlight();
        nhopCache = {{}};
        network.fit({{ animation: {{ duration: 280, easingFunction: "easeInOutCubic" }} }});
      }});
    }}

    var depthSelect = document.getElementById("depth-select");
    if (depthSelect) {{
      depthSelect.addEventListener("change", function() {{
        selectedDepth = parseInt(depthSelect.value, 10) || 1;
        nhopCache = {{}};
        if (selectedNodeId) applySelectionStyles();
        if (focusedNodeId) applySpotlightStyles();
      }});
    }}

    var edgeFilterSelect = document.getElementById("edge-filter");
    if (edgeFilterSelect) {{
      edgeFilterSelect.addEventListener("change", function() {{
        edgeFilter = edgeFilterSelect.value || "all";
        edges.forEach(function(e) {{
          var rel = e.relation || "";
          var hide = false;
          if (edgeFilter === "subClassOf") hide = rel !== "subClassOf";
          else if (edgeFilter === "type") hide = rel !== "type" && rel !== "instanceOf";
          else if (edgeFilter === "other") hide = rel === "subClassOf" || rel === "type" || rel === "instanceOf";
          edges.update({{ id: e.id, hidden: hide }});
        }});
        nhopCache = {{}};
        if (selectedNodeId) applySelectionStyles();
      }});
    }}

    /* ── Edge-label toggle ───────────────────────────────────── */

    function getRelationLabel(edge) {{
      var rel = edge && (edge.relation || edge.label) ? (edge.relation || edge.label) : "related_to";
      return showEdgeLabels ? rel : "";
    }}

    function applyEdgeLabelMode() {{
      edges.forEach(function(e) {{
        edges.update({{ id: e.id, label: getRelationLabel(e) }});
      }});
      edgeLabelToggle.textContent = "Labels: " + (showEdgeLabels ? "ON" : "OFF");
    }}

    edgeLabelToggle.addEventListener("click", function() {{
      showEdgeLabels = !showEdgeLabels;
      applyEdgeLabelMode();
    }});

    /* ── Selection / highlight ───────────────────────────────── */

    var selectedNodeId = null;

    function applySelectionStyles() {{
      var relatedNodes = null;
      var relatedEdges = null;
      if (selectedNodeId) {{
        var depth = selectedDepth >= 999 ? 10 : selectedDepth;
        relatedNodes = getConnectedNodesNHop(selectedNodeId, depth);
        relatedEdges = getConnectedEdgesForNodes(relatedNodes);
      }}

      nodes.forEach(function(n) {{
        var meta = nodeDefaults[n.id] || {{}};
        var isRelated = !selectedNodeId || (relatedNodes && relatedNodes.has(n.id));
        var isSelected = selectedNodeId === n.id;
        nodes.update({{
          id: n.id,
          borderWidth: selectedNodeId && isRelated ? 2.4 : 1.2,
          color: {{
            background: selectedNodeId ? (isRelated ? "#1e1e28" : "#0c0c12") : "#1e1e28",
            border: selectedNodeId
              ? (isRelated ? (meta.accent || "#ec4899") : "#18182a")
              : (meta.accent || "#2a2a3a"),
            highlight: {{ background: "#1e1e28", border: meta.accent || "#ec4899" }},
            hover: {{ background: "#1e1e28", border: meta.accent || "#ec4899" }}
          }},
          font: {{
            color: selectedNodeId ? (isRelated ? "#ffffff" : "#33333d") : "#e8e6e3",
            size: selectedNodeId && !isRelated ? 11 : 13,
            face: "Space Grotesk",
          }},
          shadow: isSelected
            ? {{ enabled: true, color: withAlpha(meta.accent || "#ec4899", 0.65), size: 12, x: 0, y: 0 }}
            : false,
        }});
      }});
      edges.forEach(function(e) {{
        var def = edgeDefaults[e.id] || {{}};
        var base = def.color || "#6b7280";
        var baseDashes = def.dashes || false;
        var active = !selectedNodeId || (relatedEdges && relatedEdges.has(e.id));
        edges.update({{
          id: e.id,
          label: getRelationLabel(e),
          color: {{
            color: selectedNodeId ? (active ? base : withAlpha(base, 0.06)) : base,
            opacity: selectedNodeId ? (active ? 1.0 : 0.06) : 0.88
          }},
          width: selectedNodeId ? (active ? 2.6 : 0.4) : 1.8,
          dashes: selectedNodeId ? (active ? baseDashes : [3, 6]) : baseDashes,
          font: {{
            color: selectedNodeId ? (active ? "#f8f4ff" : "#22222a") : "#b6b3bf",
            background: selectedNodeId ? (active ? "#151520" : "#101018") : "#14141a"
          }},
          isDimmed: selectedNodeId ? !active : false,
        }});
      }});
    }}

    function resetHighlight() {{
      selectedNodeId = null;
      applySelectionStyles();
    }}

    network.on("click", function(params) {{
      if (focusedNodeId) {{
        if (!params.nodes || params.nodes.length === 0) {{
          exitSpotlight();
        }}
        return;
      }}
      if (!params.nodes || params.nodes.length === 0) {{
        resetHighlight();
        return;
      }}
      selectedNodeId = params.nodes[0];
      applySelectionStyles();
    }});

    /* ── Tooltip ─────────────────────────────────────────────── */

    function buildNodeRelationSummary(nodeId) {{
      var edgeIds = network.getConnectedEdges(nodeId) || [];
      var inCount = 0;
      var outCount = 0;
      var relCounts = {{}};
      edgeIds.forEach(function(edgeId) {{
        var edge = edges.get(edgeId);
        if (!edge) return;
        if (edge.to === nodeId) inCount += 1;
        if (edge.from === nodeId) outCount += 1;
        var rel = edge.relation || edge.label || "related_to";
        relCounts[rel] = (relCounts[rel] || 0) + 1;
      }});
      var relItems = Object.entries(relCounts)
        .sort(function(a, b) {{ return b[1] - a[1]; }})
        .slice(0, 4);
      return {{
        total: edgeIds.length,
        incoming: inCount,
        outgoing: outCount,
        relItems: relItems,
      }};
    }}

    var hoverNodeId = null;
    network.on("hoverNode", function(params) {{
      var id = params.node;
      if (focusedNodeId) {{
        var spotSet = new Set(network.getConnectedNodes(focusedNodeId));
        spotSet.add(focusedNodeId);
        if (!spotSet.has(id)) return;
      }}
      var meta = nodeDefaults[id] || {{}};
      var stats = buildNodeRelationSummary(id);
      var desc = meta.description ? '<div class="desc">' + escHtml(meta.description).slice(0, 220) + '</div>' : "";
      var relPills = stats.relItems.length
        ? '<div class="rels">' + stats.relItems.map(function(item) {{
            return '<span class="rel-pill">' + escHtml(item[0]) + ' \u00d7' + item[1] + '</span>';
          }}).join('') + '</div>'
        : "";
      tooltip.innerHTML = '<div class="kind">' + escHtml(meta.kind || "node") + '</div>'
        + '<div class="name">' + escHtml(id) + '</div>'
        + '<div class="stats">'
        + '<div class="stat"><span class="v">' + stats.total + '</span><span class="k">links</span></div>'
        + '<div class="stat"><span class="v">' + stats.incoming + '</span><span class="k">in</span></div>'
        + '<div class="stat"><span class="v">' + stats.outgoing + '</span><span class="k">out</span></div>'
        + '</div>'
        + relPills
        + desc;

      var domPoint = params.event && params.event.pointer && params.event.pointer.DOM
        ? params.event.pointer.DOM
        : network.canvasToDOM(network.getPositions([id])[id]);
      var left = Math.min(domPoint.x + 16, container.clientWidth - 320);
      var top = Math.min(domPoint.y + 16, container.clientHeight - 200);
      tooltip.style.left = Math.round(Math.max(8, left)) + "px";
      tooltip.style.top = Math.round(Math.max(8, top)) + "px";
      tooltip.classList.add("visible");

      if (hoverNodeId && hoverNodeId !== id) {{
        applySelectionStyles();
      }}

      nodes.update({{
        id: id,
        borderWidth: 2.6,
        color: {{
          background: "#252533",
          border: meta.accent || "#ec4899",
          highlight: {{ background: "#252533", border: meta.accent || "#ec4899" }},
          hover: {{ background: "#252533", border: meta.accent || "#ec4899" }}
        }},
      }});
      hoverNodeId = id;
    }});

    network.on("blurNode", function() {{
      tooltip.classList.remove("visible");
      if (!hoverNodeId) return;
      if (focusedNodeId) {{ applySpotlightStyles(); }}
      else {{ applySelectionStyles(); }}
      hoverNodeId = null;
    }});

    network.on("hoverEdge", function(params) {{
      if (focusedNodeId) return;
      var edge = edges.get(params.edge);
      if (!edge) return;
      var hoverDashes = edge.isDimmed ? [2, 4] : [7, 5];
      var hoverWidth = edge.isDimmed ? 0.8 : Math.max(2.8, edge.width || 2.6);
      edges.update({{ id: edge.id, dashes: hoverDashes, width: hoverWidth }});
    }});

    network.on("blurEdge", function(params) {{
      if (focusedNodeId) return;
      var edge = edges.get(params.edge);
      if (!edge) return;
      applySelectionStyles();
    }});

    /* ── Spotlight (double-click) ────────────────────────────── */

    function applySpotlightStyles() {{
      var depth = selectedDepth >= 999 ? 10 : selectedDepth;
      var related = getConnectedNodesNHop(focusedNodeId, depth);
      var relEdges = getConnectedEdgesForNodes(related);

      nodes.forEach(function(n) {{
        var meta = nodeDefaults[n.id] || {{}};
        var inSpot = related.has(n.id);
        var isFocus = n.id === focusedNodeId;
        if (!inSpot) {{
          nodes.update({{
            id: n.id,
            borderWidth: 0,
            color: {{
              background: "rgba(0,0,0,0)",
              border: "rgba(0,0,0,0)",
              highlight: {{ background: "rgba(0,0,0,0)", border: "rgba(0,0,0,0)" }},
              hover: {{ background: "rgba(0,0,0,0)", border: "rgba(0,0,0,0)" }},
            }},
            font: {{ color: "rgba(0,0,0,0)", size: 13, face: "Space Grotesk" }},
            shadow: false,
          }});
        }} else {{
          nodes.update({{
            id: n.id,
            borderWidth: isFocus ? 2.8 : 2.0,
            color: {{
              background: isFocus ? "#252538" : "#1e1e28",
              border: meta.accent || "#ec4899",
              highlight: {{ background: "#252538", border: meta.accent || "#ec4899" }},
              hover: {{ background: "#252538", border: meta.accent || "#ec4899" }},
            }},
            font: {{ color: "#ffffff", size: 14, face: "Space Grotesk" }},
            shadow: isFocus
              ? {{ enabled: true, color: withAlpha(meta.accent || "#ec4899", 0.8), size: 22, x: 0, y: 0 }}
              : {{ enabled: true, color: withAlpha(meta.accent || "#ec4899", 0.35), size: 10, x: 0, y: 0 }},
          }});
        }}
      }});
      edges.forEach(function(e) {{
        var inSpot = relEdges.has(e.id);
        var base = edgeDefaults[e.id] ? edgeDefaults[e.id].color : "#6b7280";
        if (!inSpot) {{
          edges.update({{
            id: e.id,
            label: "",
            color: {{ color: "rgba(0,0,0,0)", opacity: 0 }},
            width: 0,
            dashes: false,
          }});
        }} else {{
          edges.update({{
            id: e.id,
            label: getRelationLabel(e),
            color: {{ color: base, opacity: 1.0 }},
            width: 3.0,
            dashes: false,
            font: {{ color: "#f8f4ff", size: 12, background: "rgba(20,20,26,0.92)", face: "JetBrains Mono", strokeWidth: 0 }},
            isDimmed: false,
          }});
        }}
      }});
    }}

    function enterSpotlight(nodeId) {{
      if (!focusedNodeId) {{
        var visCanvas = container.querySelector("canvas");
        if (visCanvas) {{
          spotlightBg.style.backgroundImage = "url(" + visCanvas.toDataURL() + ")";
        }}
        spotlightBg.classList.add("active");
        container.style.background = "transparent";
      }}
      focusedNodeId = nodeId;
      selectedNodeId = nodeId;
      applySpotlightStyles();
      network.focus(nodeId, {{
        scale: 1.15,
        animation: {{ duration: 420, easingFunction: "easeInOutCubic" }},
      }});
    }}

    function exitSpotlight() {{
      if (!focusedNodeId) return;
      focusedNodeId = null;
      selectedNodeId = null;
      spotlightBg.classList.remove("active");
      container.style.background = "";
      applySelectionStyles();
      network.fit({{ animation: {{ duration: 380, easingFunction: "easeInOutCubic" }} }});
    }}

    network.on("doubleClick", function(params) {{
      if (!params.nodes || params.nodes.length === 0) {{
        exitSpotlight();
        return;
      }}
      enterSpotlight(params.nodes[0]);
    }});

    /* ── Init ────────────────────────────────────────────────── */

    applyEdgeLabelMode();
    resetHighlight();

    var layoutSelect = document.getElementById("layout-select");
    if (layoutSelect) {{
      layoutSelect.addEventListener("change", function() {{
        layoutMode = layoutSelect.value || "force";
        if (layoutMode === "elk") {{
          if (typeof ELK === "undefined") {{
            if (DEBUG) debugLog("ELK not loaded, falling back to hierarchy");
            layoutSelect.value = "hierarchical";
            layoutMode = "hierarchical";
          }} else {{
            runElkLayout();
            return;
          }}
        }}
        var useHierarchy = layoutMode === "hierarchical";
        network.setOptions({{
          layout: {{
            hierarchical: {{
              enabled: useHierarchy,
              direction: "UD",
              sortMethod: "directed",
              levelSeparation: 180,
              nodeSpacing: 140,
              treeSpacing: 200,
            }},
          }},
          physics: {{
            enabled: true,
            hierarchicalRepulsion: useHierarchy ? {{
              centralGravity: 0.0,
              springLength: 150,
              springConstant: 0.01,
              nodeDistance: 180,
              damping: 0.09,
            }} : undefined,
            barnesHut: useHierarchy ? undefined : {{
              gravitationalConstant: -2800,
              centralGravity: 0.35,
              springLength: 140,
              springConstant: 0.06,
              damping: 0.12,
              avoidOverlap: 0.25,
            }},
            stabilization: {{ enabled: true, iterations: 250, updateInterval: 50, fit: true }},
          }},
        }});
        simulationFrozen = false;
        network.once("stabilizationIterationsDone", function() {{
          network.setOptions({{ physics: {{ enabled: false }} }});
          simulationFrozen = true;
          network.fit({{ animation: {{ duration: 300, easingFunction: "easeInOutCubic" }} }});
        }});
      }});
    }}

    function runElkLayout() {{
      if (typeof ELK === "undefined") return;
      if (hasCycles) {{
        if (DEBUG) debugLog("Graph has cycles, falling back to force layout");
        layoutSelect.value = "force";
        layoutMode = "force";
        network.setOptions({{ physics: {{ enabled: true }}, layout: {{ hierarchical: {{ enabled: false }} }} }});
        network.setOptions({{ physics: {{ barnesHut: {{ gravitationalConstant: -2800, centralGravity: 0.35, springLength: 140, springConstant: 0.06, damping: 0.12, avoidOverlap: 0.25 }}, stabilization: {{ enabled: true, iterations: 250, updateInterval: 50, fit: true }} }} }});
        simulationFrozen = false;
        network.once("stabilizationIterationsDone", function() {{
          network.setOptions({{ physics: {{ enabled: false }} }});
          simulationFrozen = true;
          network.fit({{ animation: {{ duration: 300, easingFunction: "easeInOutCubic" }} }});
        }});
        return;
      }}
      var elk = new ELK();
      var visibleNodes = nodes.get().filter(function(n) {{ return !n.hidden; }});
      var visibleEdges = edges.get().filter(function(e) {{ return !e.hidden; }});
      var nodeIds = new Set(visibleNodes.map(function(n) {{ return n.id; }}));
      var normalizedEdges = visibleEdges
        .filter(function(e) {{ return nodeIds.has(e.from) && nodeIds.has(e.to) && e.from !== e.to; }})
        .map(function(e) {{ return {{ id: String(e.id || e.from + "-" + e.to), sources: [String(e.from)], targets: [String(e.to)] }}; }});
      var nodeWidth = 140;
      var nodeHeight = 40;
      var elkGraph = {{
        id: "root",
        layoutOptions: {{
          "elk.algorithm": "layered",
          "elk.direction": "DOWN",
          "elk.spacing.nodeNode": "50",
          "elk.layered.spacing.nodeNodeBetweenLayers": "100",
          "elk.edgeRouting": "ORTHOGONAL",
          "elk.layered.allowNonTreeEdges": "true",
        }},
        children: visibleNodes.map(function(n) {{
          var w = (n.width != null && n.width > 0) ? n.width : nodeWidth;
          var h = (n.height != null && n.height > 0) ? n.height : nodeHeight;
          return {{ id: String(n.id), width: w, height: h }};
        }}),
        edges: normalizedEdges,
      }};
      elk.layout(elkGraph).then(function(layout) {{
        if (!layout || !layout.children || layout.children.length === 0) {{
          if (DEBUG) debugLog("ELK returned empty layout, fallback to force");
          fallbackToForceLayout();
          return;
        }}
        var pos = {{}};
        var allSame = true;
        var firstX = null, firstY = null;
        layout.children.forEach(function(c) {{
          var x = (c.x != null) ? c.x : 0;
          var y = (c.y != null) ? c.y : 0;
          pos[c.id] = {{ x: x, y: y }};
          if (firstX == null) {{ firstX = x; firstY = y; }}
          else if (x !== firstX || y !== firstY) allSame = false;
        }});
        if (Object.keys(pos).length === 0) {{
          if (DEBUG) debugLog("ELK produced no positions, fallback to force");
          fallbackToForceLayout();
          return;
        }}
        if (allSame && Object.keys(pos).length > 1) {{
          if (DEBUG) debugLog("ELK returned identical coordinates, fallback to force");
          fallbackToForceLayout();
          return;
        }}
        network.setPositions(pos);
        network.setOptions({{ physics: {{ enabled: false }} }});
        simulationFrozen = true;
        network.fit({{ animation: {{ duration: 300, easingFunction: "easeInOutCubic" }} }});
      }}).catch(function(err) {{
        if (DEBUG) debugLog("ELK layout failed:", err);
        fallbackToForceLayout();
      }});
    }}

    function fallbackToForceLayout() {{
      if (layoutSelect) layoutSelect.value = "force";
      layoutMode = "force";
      network.setOptions({{ layout: {{ hierarchical: {{ enabled: false }} }}, physics: {{ enabled: true, barnesHut: {{ gravitationalConstant: -2800, centralGravity: 0.35, springLength: 140, springConstant: 0.06, damping: 0.12, avoidOverlap: 0.25 }}, stabilization: {{ enabled: true, iterations: 250, updateInterval: 50, fit: true }} }} }});
      simulationFrozen = false;
      network.once("stabilizationIterationsDone", function() {{
        network.setOptions({{ physics: {{ enabled: false }} }});
        simulationFrozen = true;
        network.fit({{ animation: {{ duration: 300, easingFunction: "easeInOutCubic" }} }});
      }});
    }}

    var viewModeSelect = document.getElementById("view-mode-select");
    if (viewModeSelect) {{
      viewModeSelect.addEventListener("change", function() {{
        var mode = viewModeSelect.value;
        nodes.forEach(function(n) {{
          var hide = false;
          if (mode === "classes") hide = n.kind === "instance";
          nodes.update({{ id: n.id, hidden: hide }});
        }});
        edges.forEach(function(edge) {{
          var fromNode = nodes.get(edge.from);
          var toNode = nodes.get(edge.to);
          var rel = edge.relation || "";
          var hide = false;
          if (mode === "classes") hide = rel !== "subClassOf";
          else if (mode === "instances") hide = rel !== "type" && rel !== "instanceOf";
          if (fromNode && fromNode.hidden) hide = true;
          if (toNode && toNode.hidden) hide = true;
          edges.update({{ id: edge.id, hidden: hide }});
        }});
        network.fit({{ animation: {{ duration: 280, easingFunction: "easeInOutCubic" }} }});
      }});
    }}

    network.on("stabilizationIterationsDone", function() {{
      network.setOptions({{ physics: {{ enabled: false }} }});
      simulationFrozen = true;
      if (DEBUG) {{
        var pos = network.getPositions();
        var ids = Object.keys(pos);
        var nanCount = 0;
        var sameCount = 0;
        var prev = null;
        ids.forEach(function(id) {{
          var p = pos[id];
          if (p && (isNaN(p.x) || isNaN(p.y))) nanCount++;
          if (p && prev && p.x === prev.x && p.y === prev.y) sameCount++;
          prev = p;
        }});
        debugLog("Layout done. Positions: NaN=" + nanCount + " identical=" + sameCount);
        ids.slice(0, 3).forEach(function(id) {{
          debugLog("Pos", id, pos[id]);
        }});
      }}
      network.fit({{ animation: {{ duration: 350, easingFunction: "easeInOutCubic" }} }});
      requestAnimationFrame(function() {{
        container.classList.add("ready");
      }});
    }});
    setTimeout(function() {{
      container.classList.add("ready");
    }}, 3000);
  </script>
</body>
</html>"""
