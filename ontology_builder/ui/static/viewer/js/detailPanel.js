/**
 * Ontology Graph Viewer - Node and edge detail panel
 */

import { escHtml } from "./utils.js";

export function buildNodeRelationSummary(network, nodeId, edges) {
  const edgeIds = network.getConnectedEdges(nodeId) || [];
  let inCount = 0;
  let outCount = 0;
  const relCounts = {};
  edgeIds.forEach((edgeId) => {
    const edge = edges.get(edgeId);
    if (!edge) return;
    if (edge.to === nodeId) inCount += 1;
    if (edge.from === nodeId) outCount += 1;
    const rel = edge.relation || edge.label || "related_to";
    relCounts[rel] = (relCounts[rel] || 0) + 1;
  });
  const relItems = Object.entries(relCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  return { total: edgeIds.length, incoming: inCount, outgoing: outCount, relItems };
}

export function groupEdgesByRelation(network, nodeId, edges) {
  const edgeIds = network.getConnectedEdges(nodeId) || [];
  const groups = { Parents: [], Children: [], Instances: [], Dependencies: [], Other: [] };
  edgeIds.forEach((eid) => {
    const e = edges.get(eid);
    if (!e) return;
    const other = e.from === nodeId ? e.to : e.from;
    const item = '<a href="#" class="node-link" data-id="' + escHtml(other) + '">' + escHtml(other) + "</a>";
    if (e.relation === "subClassOf") {
      if (e.to === nodeId) groups.Parents.push(item);
      else groups.Children.push(item);
    } else if (e.relation === "type" || e.relation === "instanceOf") {
      if (e.from === nodeId) groups.Instances.push(item);
      else groups.Parents.push(item);
    } else if (e.relation === "depends_on" || e.relation === "part_of" || e.relation === "contains") {
      groups.Dependencies.push(item);
    } else groups.Other.push(item);
  });
  return groups;
}

export function renderNodeDetail(
  detailContent,
  nodeId,
  nodeDefaults,
  nodeAttrs,
  hierarchyLevels,
  clusters,
  network,
  edges,
  C,
  callbacks
) {
  const meta = nodeDefaults[nodeId] || {};
  const attrs = nodeAttrs[nodeId] || {};
  const stats = buildNodeRelationSummary(network, nodeId, edges);
  const docs = attrs.source_documents;
  const docStr = Array.isArray(docs) && docs.length ? docs.slice(0, 3).join(", ") : "—";
  const kind = (attrs.kind || meta.kind || "class").toUpperCase();
  const desc = (attrs.description || meta.description || "").slice(0, 300);
  const hierarchyLevel = hierarchyLevels[nodeId] != null ? hierarchyLevels[nodeId] : "—";
  const clusterId = clusters ? clusters.findIndex((c) => c.indexOf(nodeId) !== -1) : -1;
  const groups = groupEdgesByRelation(network, nodeId, edges);
  const relIcons = { Parents: "▲", Children: "▼", Instances: "◇", Dependencies: "◆", Other: "○" };

  let relHtml = "";
  ["Parents", "Children", "Instances", "Dependencies", "Other"].forEach((g) => {
    if (groups[g].length) {
      const count = groups[g].length;
      const collapsed = count > 5 ? " collapsed" : "";
      const items = groups[g].map((item) => "<li>" + item + "</li>").join("");
      relHtml +=
        '<div class="rel-group" data-rel="' +
        escHtml(g.toLowerCase()) +
        '">' +
        '<button type="button" class="rel-group-header">' +
        '<span class="rel-icon">' +
        (relIcons[g] || "•") +
        "</span> " +
        escHtml(g) +
        ' <span class="rel-count">' +
        count +
        "</span></button>" +
        '<ul class="rel-list' +
        collapsed +
        '">' +
        items +
        "</ul></div>";
    }
  });
  const repairTag = docStr.indexOf("repair") !== -1 ? '<span class="repair-tag">⚙ Repair</span>' : "";

  detailContent.innerHTML =
    '<div class="panel-section"><div class="detail-title">Node Overview</div>' +
    '<div class="detail-row"><span class="detail-label">Name</span><br><span class="detail-value" style="font-weight:600;">' +
    escHtml(nodeId) +
    "</span></div>" +
    '<div class="detail-row"><span class="detail-label">Type</span><br><span class="detail-value">' +
    escHtml(kind) +
    "</span> " +
    repairTag +
    "</div>" +
    (desc ? '<div class="detail-row"><span class="detail-label">Description</span><br><span class="detail-value">' + escHtml(desc) + "</span></div>" : "") +
    (docStr !== "—" ? '<div class="detail-row"><span class="detail-label">Sources</span><br><span class="detail-value">' + escHtml(docStr) + "</span></div>" : "") +
    "</div>" +
    '<div class="panel-section"><div class="detail-title">Graph Metrics</div>' +
    '<div class="detail-row"><span class="detail-label">Degree</span><br><span class="detail-value">' +
    stats.total +
    " (in: " +
    stats.incoming +
    ", out: " +
    stats.outgoing +
    ")</span></div>" +
    '<div class="detail-row"><span class="detail-label">Hierarchy Level</span><br><span class="detail-value">' +
    hierarchyLevel +
    "</span></div>" +
    (clusterId >= 0 ? '<div class="detail-row"><span class="detail-label">Cluster</span><br><span class="detail-value">' + clusterId + "</span></div>" : "") +
    "</div>" +
    (relHtml ? '<div class="panel-section"><div class="detail-title">Relationships</div>' + relHtml + "</div>" : "") +
    '<div class="panel-section"><div class="detail-title">Neighborhood</div>' +
    '<div style="display:flex;gap:6px;flex-wrap:wrap;">' +
    '<button type="button" class="ctrl-btn expand-btn" data-hops="1">Expand 1 hop</button>' +
    '<button type="button" class="ctrl-btn expand-btn" data-hops="2">Expand 2 hops</button>' +
    '<button type="button" class="ctrl-btn collapse-btn">Collapse</button>' +
    "</div></div>";

  if (callbacks) {
    detailContent.querySelectorAll(".rel-group-header").forEach((btn) => {
      btn.addEventListener("click", () => {
        const list = btn.nextElementSibling;
        if (list) list.classList.toggle("collapsed");
      });
    });
    detailContent.querySelectorAll(".node-link").forEach((a) => {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const id = a.getAttribute("data-id");
        if (id && callbacks.onNodeLinkClick) callbacks.onNodeLinkClick(id);
      });
    });
    detailContent.querySelectorAll(".expand-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const h = parseInt(btn.getAttribute("data-hops"), 10);
        if (callbacks.onExpand) callbacks.onExpand(h);
      });
    });
    detailContent.querySelectorAll(".collapse-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (callbacks.onCollapse) callbacks.onCollapse();
      });
    });
  }
}

export function renderEdgeDetail(detailContent, edgeId, edges, edgeAttrs, C, callbacks) {
  const e = edges.get(edgeId);
  if (!e) return;
  const ea = edgeAttrs[edgeId] || {};
  const sc = ea.correctness_score != null ? ea.correctness_score : 0;
  const votes = ea.cross_chunk_votes != null ? ea.cross_chunk_votes : 1;
  const pathLen = ea.derivation_path_length != null ? ea.derivation_path_length : 1;
  const pathText = pathLen === 1 ? "direct" : "inferred ×" + pathLen;
  const origin = ea.provenance_origin || "extraction";
  const rule = ea.provenance_rule || "";
  const originLabel = origin + (rule ? " (" + rule + ")" : "");
  const scoreColor = "hsl(" + sc * 120 + ", 70%, 50%)";

  detailContent.innerHTML =
    '<div class="detail-title">Edge</div>' +
    '<div class="detail-row"><span class="detail-label">Relation</span><br><span class="detail-value">' +
    escHtml(e.relation || e.label || "related_to") +
    "</span></div>" +
    '<div class="detail-row"><span class="detail-label">Correctness</span><br>' +
    '<div class="score-meter">' +
    '<div class="score-meter-bar"><div class="score-fill" style="width:' +
    sc * 100 +
    "%; background:" +
    scoreColor +
    ';"></div></div>' +
    '<span class="score-label">' +
    sc.toFixed(2) +
    "</span></div></div>" +
    '<div class="detail-row"><span class="detail-label">Votes</span><br><span class="detail-value">' +
    votes +
    "×</span></div>" +
    '<div class="detail-row"><span class="detail-label">Path</span><br><span class="detail-value">' +
    pathText +
    "</span></div>" +
    '<div class="detail-row"><span class="detail-label">Origin</span><br><span class="origin-pill">' +
    escHtml(originLabel) +
    "</span></div>" +
    '<div class="detail-row"><span class="detail-label">From</span> ' +
    escHtml(e.from) +
    ' <span class="detail-label">To</span> ' +
    escHtml(e.to) +
    "</div>" +
    '<button type="button" class="ctrl-btn flag-incorrect-btn" style="margin-top:8px;" title="Mark for review">Flag as incorrect</button>';
  if (callbacks?.onFlagIncorrect) {
    detailContent.querySelector(".flag-incorrect-btn")?.addEventListener("click", () => callbacks.onFlagIncorrect());
  }
}
