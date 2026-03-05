"""Graph visualization: Matplotlib PNG and interactive vis.js HTML.

Differentiates classes (rectangles/blue) from instances (circles/green),
colors edges by relation type.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

if TYPE_CHECKING:
    from ontology_builder.storage.graphdb import OntologyGraph

_RELATION_COLORS: dict[str, str] = {
    "subClassOf": "#ec4899",
    "type": "#38bdf8",
    "part_of": "#38bdf8",
    "contains": "#a78bfa",
    "depends_on": "#f59e0b",
}
_DEFAULT_EDGE_COLOR = "#6b7280"


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


def generate_visjs_html(graph: "OntologyGraph") -> str:
    """Generate standalone HTML page with interactive vis.js graph viewer."""
    g = graph.get_graph()

    vis_nodes: list[dict[str, Any]] = []
    for node in g.nodes():
        data = g.nodes[node]
        kind = data.get("kind", "class")
        label = node
        desc = data.get("description", "")
        accent = "#ec4899" if kind == "class" else "#38bdf8" if kind == "instance" else "#8a8a94"
        vis_nodes.append({
            "id": node,
            "baseLabel": label,
            "label": label,
            "kind": kind,
            "accent": accent,
            "description": desc,
        })

    vis_edges: list[dict[str, Any]] = []
    for u, v, data in g.edges(data=True):
        rel = data.get("relation", "related_to")
        color = _RELATION_COLORS.get(rel, _DEFAULT_EDGE_COLOR)
        vis_edges.append({
            "id": f"{u}->{v}:{rel}",
            "from": u,
            "to": v,
            "label": rel,
            "relation": rel,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": color, "opacity": 0.96, "highlight": color, "hover": color},
            "width": 1.8,
            "smooth": {"type": "continuous"},
            "font": {
                "size": 11,
                "align": "middle",
                "face": "JetBrains Mono",
                "color": "#ddd9e6",
                "background": "#14141a",
                "strokeWidth": 0,
            },
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)
    stats = graph.export().get("stats", {})
    edges_count = stats.get("edges")
    if edges_count is None:
        edges_count = stats.get("relations")
    if edges_count is None:
        edges_count = len(vis_edges)
    stats_html = (
        f"Classes: {stats.get('classes', 0)} | "
        f"Instances: {stats.get('instances', 0)} | "
        f"Edges: {edges_count} | "
        f"Axioms: {stats.get('axioms', 0)}"
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ontology Graph Viewer</title>
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js" onerror="window.__viewerScriptError=true"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif; background: #0a0a0f; color: #e8e6e3; min-height: 100vh; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    #app {{ min-height: 100vh; display: flex; flex-direction: column; }}
    #header {{ padding: 14px 22px; background: #14141a; border-bottom: 1px solid #1a1a24; display: flex; justify-content: space-between; align-items: center; gap: 18px; }}
    #header h1 {{ font-size: 18px; font-weight: 600; color: #e8e6e3; }}
    #stats {{ font-size: 12px; color: #8a8a94; margin-top: 3px; }}
    #controls {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .ctrl-item {{ display: flex; align-items: center; gap: 6px; font-size: 11px; color: #8a8a94; background: #1e1e28; border: 1px solid #2a2a3a; border-radius: 8px; padding: 5px 8px; }}
    .ctrl-btn {{ cursor: pointer; transition: border-color 0.2s ease, color 0.2s ease, background 0.18s ease; }}
    .ctrl-btn:hover {{ border-color: rgba(236,72,153,0.4); color: #e8e6e3; }}
    .ctrl-btn.active {{ border-color: rgba(56,189,248,0.6); color: #dff4ff; background: rgba(56,189,248,0.08); }}
    .ctrl-sep {{ width: 1px; height: 20px; background: #2a2a3a; margin: 0 2px; }}
    .legend-dot {{ width: 11px; height: 11px; border-radius: 2px; }}
    #graph-wrap {{ flex: 1; padding: 12px; position: relative; }}
    #graph {{
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
        <button id="fit-btn" class="ctrl-item ctrl-btn" type="button">Fit</button>
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
      }};
    }});

    /* ── Network setup ───────────────────────────────────────── */

    var options = {{
      autoResize: true,
      physics: {{
        enabled: true,
        barnesHut: {{
          gravitationalConstant: -3000,
          centralGravity: 0.3,
          springLength: 160,
          springConstant: 0.05,
          damping: 0.09,
          avoidOverlap: 0.2,
        }},
        stabilization: {{
          enabled: true,
          iterations: 600,
          updateInterval: 25,
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
        relatedNodes = new Set(network.getConnectedNodes(selectedNodeId));
        relatedNodes.add(selectedNodeId);
        relatedEdges = new Set(network.getConnectedEdges(selectedNodeId));
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
        var base = edgeDefaults[e.id] ? edgeDefaults[e.id].color : "#6b7280";
        var active = !selectedNodeId || (relatedEdges && relatedEdges.has(e.id));
        edges.update({{
          id: e.id,
          label: getRelationLabel(e),
          color: {{
            color: selectedNodeId ? (active ? base : withAlpha(base, 0.06)) : base,
            opacity: selectedNodeId ? (active ? 1.0 : 0.06) : 0.88
          }},
          width: selectedNodeId ? (active ? 2.6 : 0.4) : 1.8,
          dashes: selectedNodeId ? (active ? false : [3, 6]) : false,
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
      var related = new Set(network.getConnectedNodes(focusedNodeId));
      related.add(focusedNodeId);
      var relEdges = new Set(network.getConnectedEdges(focusedNodeId));

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
    network.on("stabilizationIterationsDone", function() {{
      network.setOptions({{ physics: {{ enabled: false }} }});
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
